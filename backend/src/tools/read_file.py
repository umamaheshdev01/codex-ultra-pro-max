import os

schema = {
    "name": "read_file",
    "description": "Read a UTF-8 text file relative to the project root.",
    "parameters": {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "File path relative to the project root.",
            }
        },
        "required": ["path"],
        "additionalProperties": False,
    },
}


def _resolve_project_path(project_root: str, path: str) -> str:
    root = os.path.abspath(project_root)
    resolved = os.path.abspath(os.path.join(root, path))

    if os.path.commonpath([root, resolved]) != root:
        raise ValueError("Path must stay inside project_root")

    return resolved


async def execute(args: dict, project_root: str) -> str:
    path = args.get("path")
    if not isinstance(path, str) or not path:
        raise ValueError("path must be a non-empty string")

    resolved = _resolve_project_path(project_root, path)
    with open(resolved, "r", encoding="utf-8", errors="replace") as file:
        return file.read(20_000)
