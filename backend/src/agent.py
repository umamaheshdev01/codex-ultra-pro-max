import json
import os
from pathlib import Path

from openai import AsyncOpenAI
from dotenv import dotenv_values

from src.mcp_manager import MCPManager
from src.tools import TOOL_SCHEMAS, execute_tool

DEFAULT_OPENAI_BASE_URL = "https://api.openai.com/v1"


def _create_openai_client():
    env_path = Path(__file__).resolve().parents[2] / ".env"
    env_values = dotenv_values(env_path)
    api_key = env_values.get("OPENAI_API_KEY") or os.environ.get("OPENAI_API_KEY")
    base_url = env_values.get("OPENAI_BASE_URL") or DEFAULT_OPENAI_BASE_URL

    return AsyncOpenAI(api_key=api_key, base_url=base_url)


async def run_agent(
    messages,
    project_root,
    on_tool_call,
    mcp_manager: MCPManager | None = None,
):
    client = _create_openai_client()
    tools = TOOL_SCHEMAS
    if mcp_manager:
        tools = TOOL_SCHEMAS + mcp_manager.get_openai_schemas()

    while True:
        stream = await client.chat.completions.create(
            model="gpt-4o",
            tools=tools,
            messages=messages,
            stream=True,
        )
        full_content = ""
        tool_calls_raw = {}

        async for chunk in stream:
            delta = chunk.choices[0].delta
            if delta.content:
                full_content += delta.content
                yield {"type": "token", "content": delta.content}
            if delta.tool_calls:
                for tc in delta.tool_calls:
                    i = tc.index
                    if i not in tool_calls_raw:
                        tool_calls_raw[i] = {"id": "", "name": "", "arguments": ""}
                    if tc.id:
                        tool_calls_raw[i]["id"] += tc.id
                    if tc.function.name:
                        tool_calls_raw[i]["name"] += tc.function.name
                    if tc.function.arguments:
                        tool_calls_raw[i]["arguments"] += tc.function.arguments

        assistant_msg = {"role": "assistant", "content": full_content}
        if tool_calls_raw:
            assistant_msg["tool_calls"] = [
                {
                    "id": t["id"],
                    "type": "function",
                    "function": {"name": t["name"], "arguments": t["arguments"]},
                }
                for t in tool_calls_raw.values()
            ]
        messages.append(assistant_msg)

        if not tool_calls_raw:
            break

        for t in tool_calls_raw.values():
            args = json.loads(t["arguments"])
            tool_name = t["name"]
            if mcp_manager and tool_name in mcp_manager.tool_to_server:
                result = await mcp_manager.execute(tool_name, args)
            else:
                result = await execute_tool(tool_name, args, project_root)

            await on_tool_call(tool_name, args, result)
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": t["id"],
                    "content": result,
                }
            )

    yield {"type": "done"}
