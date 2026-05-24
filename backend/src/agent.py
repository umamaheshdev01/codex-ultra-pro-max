import json

from openai import AsyncOpenAI

from src.tools import TOOL_SCHEMAS, execute_tool


async def run_agent(messages, project_root, on_tool_call):
    client = AsyncOpenAI()
    while True:
        stream = await client.chat.completions.create(
            model="gpt-4o",
            tools=TOOL_SCHEMAS,
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
            result = await execute_tool(t["name"], args, project_root)
            await on_tool_call(t["name"], args, result)
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": t["id"],
                    "content": result,
                }
            )

    yield {"type": "done"}
