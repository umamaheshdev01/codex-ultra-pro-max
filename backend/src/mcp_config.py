import json
from pathlib import Path
from typing import Literal, Optional

from pydantic import BaseModel, Field


MCP_CONFIG_FILE_NAME = ".codex-mcp.json"


class MCPServerConfig(BaseModel):
    name: str
    transport: Literal["stdio", "sse"]
    command: Optional[list[str]] = None
    url: Optional[str] = None
    env: Optional[dict[str, str]] = None


class MCPConfig(BaseModel):
    servers: list[MCPServerConfig] = Field(default_factory=list)


def _load_config_file(config_path: Path) -> MCPConfig:
    if not config_path.exists():
        return MCPConfig()

    with config_path.open("r", encoding="utf-8") as file:
        return MCPConfig.model_validate(json.load(file))


def load_mcp_config(project_root: str, fallback_root: str | None = None) -> MCPConfig:
    config_paths = []
    project_config_path = Path(project_root).resolve() / MCP_CONFIG_FILE_NAME
    config_paths.append(project_config_path)

    if fallback_root:
        fallback_config_path = Path(fallback_root).resolve() / MCP_CONFIG_FILE_NAME
        if fallback_config_path != project_config_path:
            config_paths.append(fallback_config_path)

    servers: list[MCPServerConfig] = []
    seen_names: set[str] = set()
    for config_path in config_paths:
        config = _load_config_file(config_path)
        for server in config.servers:
            if server.name in seen_names:
                continue
            servers.append(server)
            seen_names.add(server.name)

    return MCPConfig(servers=servers)
