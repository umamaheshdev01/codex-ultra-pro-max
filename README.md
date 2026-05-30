# Helix

Custom terminal-first coding agent workspace.

## Repository Structure

```text
backend/
cli/
```

## Workspace Setup

This repository uses a Python FastAPI backend and a Node.js CLI workspace.

Start the backend:

```bash
make dev
```

This runs:

```bash
cd backend && ./.venv/bin/python -m uvicorn src.main:app --reload --port 3001
```

The Makefiles run uvicorn through `backend/.venv/bin/python`, so create the backend venv before using `make dev`.

After setup, run Helix from the project folder:

```bash
helix
```

That starts the backend if it is not already running, waits for it to become ready, and opens the interactive terminal chat.

If `helix` is not on your `PATH` yet, run this once from the repository root:

```bash
npm link
```

You can also run:

```bash
npm run install-global
```

## Environment

Copy `.env.example` to `.env` and set:

```text
OPENAI_API_KEY=
```

Backend configuration is loaded from the root `.env` with `python-dotenv`.

The CLI reads its defaults from `.helix.json` in the project root:

```json
{
  "backendUrl": "http://localhost:3001",
  "projectRoot": "/absolute/path/to/project"
}
```

## Backend

The backend is a FastAPI service in `backend/`.

```text
backend/src/
  main.py
  agent.py
  session.py
  tools/
    read_file.py
    write_file.py
    run_command.py
    list_dir.py
```

### Setup

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Development

```bash
cd backend
make dev
```

The API runs on port `3001`.

### Health Check

```text
GET /health
```

Returns:

```json
{"ok": true}
```

### Chat

```text
POST /chat
```

Request body:

```json
{
  "session_id": "default",
  "message": "List the project files",
  "project_root": "/absolute/path/to/project"
}
```

Returns Server-Sent Events with `data: {...}` JSON payloads for streamed tokens, tool calls, completion, or errors.

Clear a session over HTTP:

```text
POST /clear
```

```json
{
  "session_id": "default"
}
```

### Backend Tools

Each backend tool module exports:

- `schema`: an OpenAI function schema dict
- `async execute(args: dict, project_root: str) -> str`

Available tools:

- `read_file`: reads a file relative to `project_root`, capped at 20,000 characters
- `write_file`: writes content to a relative path and creates parent directories
- `run_command`: runs a shell command in `project_root`, times out after 30 seconds, and caps output at 8,000 characters
- `list_dir`: returns an indented project tree while skipping `node_modules`, `.git`, `__pycache__`, `venv`, and `.venv`

Path-based tools reject paths that resolve outside `project_root`.

`backend/src/tools/__init__.py` exports `TOOL_SCHEMAS` and `execute_tool(name, args, project_root)` for agent dispatch. Tool execution errors are returned as `Error: ...` strings.

### Agent

`backend/src/agent.py` exports `run_agent(messages, project_root, on_tool_call)`, an async generator that streams OpenAI tokens as `{"type": "token", "content": "..."}` events, executes requested tools, appends tool results to `messages`, and ends with `{"type": "done"}`.

### Sessions

`backend/src/session.py` exports `SessionStore`, an in-memory `session_id -> messages` store. New and cleared sessions start with the coding assistant system prompt, and inactive sessions expire after 2 hours.

## CLI

The Helix CLI package lives in `cli/` and uses Commander, Chalk, Ora, and Dotenv.

`cli/src/api.js` exports `streamChat(message, sessionId, projectRoot, backendUrl)`, an async generator that posts to `/chat`, reads Server-Sent Events, and yields parsed JSON events.

`cli/src/render.js` exports terminal rendering helpers for streamed tokens, tool calls, errors, and the CLI banner.

On `chat` startup, the CLI reads `.helix.json` from the project root. `backendUrl` and `projectRoot` from that file become defaults, and explicit `--backend` or `--project` flags override them. If `.helix.json` is missing in an interactive terminal, the CLI offers to create it:

```json
{
  "backendUrl": "http://localhost:3001",
  "projectRoot": "/absolute/path/to/project"
}
```

### Development

```bash
npm install
npm run dev --workspace cli
```

Run the health command:

```bash
npm run dev --workspace cli -- health
```

Run Helix directly during development:

```bash
npm run helix
```

Start an interactive chat:

```bash
npm run dev --workspace cli -- chat --project /absolute/path/to/project --backend http://localhost:3001
```

Run one message and exit:

```bash
npm run dev --workspace cli -- chat "List the project files"
```

In interactive mode, type `/clear` to reset the session and `/exit` to quit. `clear` and `exit` also work.

After `npm install`, the CLI binary is available as `helix` when the package is linked or installed as a command.

## MCP

Helix loads MCP servers from `.codex-mcp.json` in the target project folder. No MCP servers are bundled by default.

Example project config:

```json
{
  "servers": [
    {
      "name": "filesystem",
      "transport": "stdio",
      "command": ["npx", "-y", "@modelcontextprotocol/server-filesystem", "/tmp"]
    }
  ]
}
```

Inspect connected MCP tools:

```bash
curl http://localhost:3001/mcp/tools
```
