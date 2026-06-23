import os
from pathlib import Path
from typing import Any

import yaml
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client


class MCPBridge:
    def __init__(self, config_path: Path):
        self.config_path = config_path

    def _server(self, name: str) -> dict[str, Any]:
        config = yaml.safe_load(self.config_path.read_text(encoding="utf-8"))
        server = config.get("servers", {}).get(name)
        if not server:
            raise ValueError("Unknown MCP server")
        return server

    async def call(
        self, server_name: str, tool_name: str, arguments: dict[str, Any]
    ) -> dict[str, Any]:
        server = self._server(server_name)
        if tool_name not in server.get("allowed_tools", []):
            raise ValueError("MCP tool is not allowlisted")
        headers: dict[str, str] = {}
        token_env = server.get("bearer_token_env")
        if token_env:
            token = os.environ.get(token_env)
            if not token:
                raise ValueError(f"Missing MCP credential: {token_env}")
            headers["Authorization"] = f"Bearer {token}"

        async with streamable_http_client(
            server["url"], headers=headers
        ) as (read_stream, write_stream, _):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                result = await session.call_tool(tool_name, arguments=arguments)
                return result.model_dump(mode="json")
