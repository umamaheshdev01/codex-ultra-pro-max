import os
import asyncio

from mcp import ClientSession, StdioServerParameters
from mcp.client.sse import sse_client
from mcp.client.stdio import stdio_client

from src.mcp_config import MCPServerConfig

MCP_CONNECT_TIMEOUT_SECONDS = 60


class MCPManager:
    def __init__(self):
        self.sessions: dict[str, ClientSession] = {}
        self.tool_to_server: dict[str, str] = {}
        self._raw_tools: list = []
        self._context_managers: list = []
        self.server_status: dict[str, dict[str, str]] = {}
        self.is_connecting = False

    async def connect(self, configs: list[MCPServerConfig]):
        self.is_connecting = True
        for cfg in configs:
            self.server_status[cfg.name] = {"status": "connecting", "error": ""}
            try:
                await asyncio.wait_for(
                    self._connect_server(cfg),
                    timeout=MCP_CONNECT_TIMEOUT_SECONDS,
                )
            except Exception as e:
                error = str(e)
                if isinstance(e, asyncio.TimeoutError):
                    error = (
                        f"connection timed out after {MCP_CONNECT_TIMEOUT_SECONDS}s. "
                        "The MCP package may still be downloading or the server did not initialize."
                    )
                self.server_status[cfg.name] = {
                    "status": "failed",
                    "error": error,
                }
                print(f"MCP connect failed for {cfg.name}: {error}")
        self.is_connecting = False

    async def _connect_server(self, cfg: MCPServerConfig):
        if cfg.transport == "stdio":
            if not cfg.command:
                raise ValueError("stdio MCP server requires command")

            params = StdioServerParameters(
                command=cfg.command[0],
                args=cfg.command[1:],
                env={**os.environ, **(cfg.env or {})},
            )
            cm = stdio_client(params)
        else:
            if not cfg.url:
                raise ValueError("sse MCP server requires url")

            cm = sse_client(cfg.url)

        read, write = await cm.__aenter__()
        self._context_managers.append(cm)

        session = ClientSession(read, write)
        await session.initialize()
        self.sessions[cfg.name] = session

        result = await session.list_tools()
        for tool in result.tools:
            self.tool_to_server[tool.name] = cfg.name
            self._raw_tools.append((cfg.name, tool))
        self.server_status[cfg.name] = {"status": "connected", "error": ""}

    def get_openai_schemas(self) -> list[dict]:
        schemas = []
        for server_name, tool in self._raw_tools:
            schemas.append(
                {
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": f"[{server_name}] {tool.description or ''}",
                        "parameters": tool.inputSchema or {"type": "object"},
                    },
                }
            )
        return schemas

    def list_tools(self) -> list[dict]:
        return [
            {
                "server": server_name,
                "name": tool.name,
                "description": tool.description,
                "input_schema": tool.inputSchema or {"type": "object"},
            }
            for server_name, tool in self._raw_tools
        ]

    async def execute(self, tool_name: str, args: dict) -> str:
        server_name = self.tool_to_server.get(tool_name)
        if not server_name:
            return f"Error: unknown MCP tool {tool_name}"

        session = self.sessions[server_name]
        result = await session.call_tool(tool_name, args)

        return "\n".join(
            block.text for block in result.content if hasattr(block, "text")
        )

    async def disconnect(self):
        for cm in reversed(self._context_managers):
            await cm.__aexit__(None, None, None)

        self._context_managers.clear()
        self.sessions.clear()
        self.tool_to_server.clear()
        self._raw_tools.clear()
        self.server_status.clear()
        self.is_connecting = False
