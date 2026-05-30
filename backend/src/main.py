import asyncio
import json
import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from src.agent import run_agent
from src.mcp_config import load_mcp_config
from src.mcp_manager import MCPManager
from src.session import SessionStore
from src.skills import SkillRegistry

app = FastAPI(title="helix backend")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
skill_registry = SkillRegistry()
session_store = SessionStore(skill_registry)
mcp_manager = MCPManager()
mcp_connect_task: asyncio.Task | None = None

SKILL_ALIASES = {
    "review": "code_review",
    "code review": "code_review",
    "test": "test_writer",
    "tests": "test_writer",
    "testing": "test_writer",
    "write tests": "test_writer",
    "explain": "explain",
    "refactor": "refactor",
    "debug": "debug",
    "scaffold": "scaffold",
}


def _default_project_root() -> str:
    return str(Path(__file__).resolve().parents[2])


def _mcp_project_root() -> str:
    return os.environ.get("HELIX_PROJECT_ROOT") or _default_project_root()


class ChatRequest(BaseModel):
    session_id: str
    message: str
    project_root: str
    skill_name: str | None = None


class ClearRequest(BaseModel):
    session_id: str


@app.get("/health")
def health() -> dict[str, bool]:
    return {"ok": True}


@app.get("/skills")
def skills():
    return [
        {
            "name": skill.name,
            "description": skill.description,
            "icon": skill.icon,
        }
        for skill in skill_registry.list()
    ]


@app.on_event("startup")
async def startup():
    global mcp_connect_task
    config = load_mcp_config(_mcp_project_root(), _default_project_root())
    if config.servers:
        mcp_connect_task = asyncio.create_task(mcp_manager.connect(config.servers))


@app.on_event("shutdown")
async def shutdown():
    if mcp_connect_task and not mcp_connect_task.done():
        mcp_connect_task.cancel()
        try:
            await mcp_connect_task
        except asyncio.CancelledError:
            pass
    await mcp_manager.disconnect()


def _sse_event(payload: dict) -> str:
    return f"data: {json.dumps(payload)}\n\n"


async def _chat_events(
    session_id: str,
    message: str,
    project_root: str,
    skill_name: str | None = None,
):
    resolved_skill_name = _resolve_skill_name(session_id, skill_name, message)
    messages = session_store.get_or_create(session_id, resolved_skill_name)
    session_store.append(
        session_id,
        {"role": "user", "content": message},
        resolved_skill_name,
    )
    pending_tool_events = []
    active_skill = session_store.active_skill(session_id)
    if active_skill:
        yield {"type": "skill", "name": active_skill}

    async def on_tool_call(name, args, result):
        pending_tool_events.append(
            {
                "type": "tool_call",
                "name": name,
                "args": args,
                "result": result,
            }
        )

    async for event in run_agent(messages, project_root, on_tool_call, mcp_manager):
        while pending_tool_events:
            yield pending_tool_events.pop(0)
        yield event


def _resolve_skill_name(
    session_id: str,
    skill_name: str | None,
    message: str,
) -> str | None:
    explicit_skill = session_store.resolve_skill_name(skill_name)
    if explicit_skill:
        return explicit_skill

    normalized_message = message.strip().lower()
    if normalized_message.startswith("@"):
        candidate = normalized_message.split(maxsplit=1)[0][1:]
        return session_store.resolve_skill_name(candidate)

    for skill in skill_registry.list():
        if normalized_message.startswith(f"{skill.name} "):
            return skill.name
        if normalized_message.startswith(f"use {skill.name} "):
            return skill.name
        if normalized_message.startswith(f"with {skill.name} "):
            return skill.name

    for alias, target in SKILL_ALIASES.items():
        if normalized_message.startswith(f"{alias} "):
            return target
        if normalized_message.startswith(f"use {alias} "):
            return target
        if normalized_message.startswith(f"with {alias} "):
            return target

    return session_store.active_skill(session_id)


@app.post("/chat")
async def chat(request: ChatRequest):
    async def event_generator():
        try:
            async for event in _chat_events(
                request.session_id,
                request.message,
                request.project_root,
                request.skill_name,
            ):
                yield _sse_event(event)
        except Exception as e:
            yield _sse_event({"type": "error", "content": str(e)})

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.post("/clear")
async def clear(request: ClearRequest):
    session_store.clear(request.session_id)
    return {"ok": True, "session_id": request.session_id}


@app.get("/mcp/tools")
def mcp_tools():
    tools = mcp_manager.list_tools()
    servers = [
        {
            "name": server_name,
            "status": mcp_manager.server_status.get(
                server_name,
                {"status": "connected", "error": ""},
            )["status"],
            "error": mcp_manager.server_status.get(
                server_name,
                {"status": "connected", "error": ""},
            )["error"],
            "tools": [
                {
                    "name": tool["name"],
                    "description": tool["description"],
                    "input_schema": tool["input_schema"],
                }
                for tool in tools
                if tool["server"] == server_name
            ],
        }
        for server_name in sorted(mcp_manager.server_status.keys())
    ]

    return {"connecting": mcp_manager.is_connecting, "servers": servers}
