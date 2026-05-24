import os

schema = {
    "name": "write_file",
    "description": "Write UTF-8 text content to a file relative to the project root.",
    "parameters": {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "File path relative to the project root.",
            },
            "content": {
                "type": "string",
                "description": "Text content to write.",
            },
        },
        "required": ["path", "content"],
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
    content = args.get("content")

    if not isinstance(path, str) or not path:
        raise ValueError("path must be a non-empty string")
    if not isinstance(content, str):
        raise ValueError("content must be a string")

    resolved = _resolve_project_path(project_root, path)
    parent_dir = os.path.dirname(resolved)
    if parent_dir:
        os.makedirs(parent_dir, exist_ok=True)

    with open(resolved, "w", encoding="utf-8") as file:
        file.write(content)

    return f"Wrote {len(content)} characters to {path}"
