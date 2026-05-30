"""Tool registry and dispatcher for backend agent tools."""

from src.tools import list_dir, read_file, run_command, write_file

TOOL_MODULES = {
    read_file.schema["name"]: read_file,
    write_file.schema["name"]: write_file,
    run_command.schema["name"]: run_command,
    list_dir.schema["name"]: list_dir,
}

TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": tool.schema,
    }
    for tool in TOOL_MODULES.values()
]


async def execute_tool(name: str, args: dict, project_root: str) -> str:
    try:
        tool = TOOL_MODULES.get(name)
        if tool is None:
            raise ValueError(f"Unknown tool: {name}")
        return await tool.execute(args, project_root)
    except Exception as e:
        return f"Error: {e}"
