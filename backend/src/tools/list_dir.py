import os

schema = {
    "name": "list_dir",
    "description": "Return an indented tree of files under the project root.",
    "parameters": {
        "type": "object",
        "properties": {},
        "additionalProperties": False,
    },
}

SKIPPED_DIRS = {"node_modules", ".git", "__pycache__", "venv", ".venv"}


def _resolve_project_root(project_root: str) -> str:
    root = os.path.abspath(project_root)
    if not os.path.isdir(root):
        raise ValueError("project_root must be an existing directory")
    return root


async def execute(args: dict, project_root: str) -> str:
    root = _resolve_project_root(project_root)
    lines = [f"{os.path.basename(root)}/"]

    for current_root, dirnames, filenames in os.walk(root):
        current_root = os.path.abspath(current_root)
        if os.path.commonpath([root, current_root]) != root:
            raise ValueError("Path must stay inside project_root")

        dirnames[:] = sorted(
            dirname for dirname in dirnames if dirname not in SKIPPED_DIRS
        )
        filenames = sorted(filenames)

        relative_root = os.path.relpath(current_root, root)
        depth = 0 if relative_root == "." else relative_root.count(os.sep) + 1
        indent = "  " * depth

        for dirname in dirnames:
            lines.append(f"{indent}{dirname}/")
        for filename in filenames:
            lines.append(f"{indent}{filename}")

    return "\n".join(lines)
