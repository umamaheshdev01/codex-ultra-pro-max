import json

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from src.agent import run_agent
from src.session import SessionStore

app = FastAPI(title="codex-ultra-pro-max backend")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
session_store = SessionStore()


class ChatRequest(BaseModel):
    session_id: str
    message: str
    project_root: str


@app.get("/health")
def health() -> dict[str, bool]:
    return {"ok": True}


def _sse_event(payload: dict) -> str:
    return f"data: {json.dumps(payload)}\n\n"


async def _chat_events(session_id: str, message: str, project_root: str):
    messages = session_store.get_or_create(session_id)
    session_store.append(
        session_id,
        {"role": "user", "content": message},
    )

    async def on_tool_call(name, args, result):
        return None

    async for event in run_agent(messages, project_root, on_tool_call):
        yield event


@app.post("/chat")
async def chat(request: ChatRequest):
    async def event_generator():
        try:
            async for event in _chat_events(
                request.session_id,
                request.message,
                request.project_root,
            ):
                yield _sse_event(event)
        except Exception as e:
            yield _sse_event({"type": "error", "content": str(e)})

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.websocket("/ws")
async def websocket_chat(websocket: WebSocket):
    await websocket.accept()

    try:
        while True:
            payload = await websocket.receive_json()
            message_type = payload.get("type")

            if message_type == "chat":
                session_id = payload.get("session_id")
                message = payload.get("message")
                project_root = payload.get("project_root")

                if not session_id or not message or not project_root:
                    await websocket.send_json(
                        {
                            "type": "error",
                            "content": "session_id, message, and project_root are required",
                        }
                    )
                    continue

                try:
                    async for event in _chat_events(session_id, message, project_root):
                        await websocket.send_json(event)
                except Exception as e:
                    await websocket.send_json({"type": "error", "content": str(e)})

            elif message_type == "clear":
                session_id = payload.get("session_id")
                if not session_id:
                    await websocket.send_json(
                        {"type": "error", "content": "session_id is required"}
                    )
                    continue

                session_store.clear(session_id)
                await websocket.send_json({"type": "cleared", "session_id": session_id})

            else:
                await websocket.send_json(
                    {"type": "error", "content": f"Unknown message type: {message_type}"}
                )
    except WebSocketDisconnect:
        return
