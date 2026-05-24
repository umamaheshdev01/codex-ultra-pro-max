import asyncio
import os

schema = {
    "name": "run_command",
    "description": "Run a shell command from the project root and return combined output.",
    "parameters": {
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "description": "Shell command to run from the project root.",
            }
        },
        "required": ["command"],
        "additionalProperties": False,
    },
}

MAX_OUTPUT_CHARS = 8_000
TIMEOUT_SECONDS = 30


def _resolve_project_root(project_root: str) -> str:
    root = os.path.abspath(project_root)
    if not os.path.isdir(root):
        raise ValueError("project_root must be an existing directory")
    return root


def _cap_output(output: str) -> str:
    if len(output) <= MAX_OUTPUT_CHARS:
        return output
    return output[:MAX_OUTPUT_CHARS]


async def execute(args: dict, project_root: str) -> str:
    command = args.get("command")
    if not isinstance(command, str) or not command:
        raise ValueError("command must be a non-empty string")

    root = _resolve_project_root(project_root)
    process = await asyncio.create_subprocess_shell(
        command,
        cwd=root,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    try:
        stdout, stderr = await asyncio.wait_for(
            process.communicate(),
            timeout=TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError:
        process.kill()
        stdout, stderr = await process.communicate()
        timeout_message = f"Command timed out after {TIMEOUT_SECONDS}s.\n"
    else:
        timeout_message = ""

    combined = (
        timeout_message
        + stdout.decode("utf-8", errors="replace")
        + stderr.decode("utf-8", errors="replace")
    )
    return _cap_output(combined)
