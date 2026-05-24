# codex-ultra-pro-max

Custom Codex-like project workspace.

## Repository Structure

```text
backend/
cli/
web/
```

## Workspace Setup

This repository is configured as a Node.js monorepo using root `package.json` workspaces:

- `backend`
- `cli`
- `web`

## Environment

Copy `.env.example` to `.env` and set:

```text
OPENAI_API_KEY=
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

Development CORS allows `http://localhost:3000` and `*`, with all methods and headers enabled.

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

Returns Server-Sent Events with `data: {...}` JSON payloads for streamed tokens, completion, or errors.

### WebSocket

```text
WS /ws
```

Chat message:

```json
{
  "type": "chat",
  "session_id": "default",
  "message": "List the project files",
  "project_root": "/absolute/path/to/project"
}
```

Clear a session:

```json
{
  "type": "clear",
  "session_id": "default"
}
```

The socket sends each agent event as JSON.

### Backend Tools

Each backend tool module exports:

- `schema`: an OpenAI function schema dict
- `async execute(args: dict, project_root: str) -> str`

Available tools:

- `read_file`: reads a file relative to `project_root`, capped at 20,000 characters
- `write_file`: writes content to a relative path and creates parent directories
- `run_command`: runs a shell command in `project_root`, times out after 30 seconds, and caps output at 8,000 characters
- `list_dir`: returns an indented project tree while skipping `node_modules`, `.git`, `.next`, `__pycache__`, `venv`, and `.venv`

Path-based tools reject paths that resolve outside `project_root`.

`backend/src/tools/__init__.py` exports `TOOL_SCHEMAS` and `execute_tool(name, args, project_root)` for agent dispatch. Tool execution errors are returned as `Error: ...` strings.

### Agent

`backend/src/agent.py` exports `run_agent(messages, project_root, on_tool_call)`, an async generator that streams OpenAI tokens as `{"type": "token", "content": "..."}` events, executes requested tools, appends tool results to `messages`, and ends with `{"type": "done"}`.

### Sessions

`backend/src/session.py` exports `SessionStore`, an in-memory `session_id -> messages` store. New and cleared sessions start with the coding assistant system prompt, and inactive sessions expire after 2 hours.

## CLI

The CLI package lives in `cli/` and uses Commander, Chalk, Ora, and Dotenv.

### Development

```bash
npm install
npm run dev --workspace cli
```

Run the starter health command:

```bash
npm run dev --workspace cli -- health
```
