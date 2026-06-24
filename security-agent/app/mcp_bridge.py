import os
import ssl
from pathlib import Path
from typing import Any

import httpx
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

    @staticmethod
    def _tool_is_allowed(server: dict[str, Any], tool_name: str) -> bool:
        allowed = server.get("allowed_tools", [])
        return "*" in allowed or tool_name in allowed

    @staticmethod
    def _headers(server: dict[str, Any]) -> dict[str, str]:
        headers: dict[str, str] = {}
        token_env = server.get("bearer_token_env")
        if token_env:
            token = os.environ.get(token_env)
            if not token:
                raise ValueError(f"Missing MCP credential: {token_env}")
            headers["Authorization"] = f"Bearer {token}"
        return headers

    @staticmethod
    def _tls_verify(server: dict[str, Any]) -> ssl.SSLContext | bool:
        ca_cert = server.get("ca_cert")
        if not ca_cert:
            return True
        ca_path = Path(str(ca_cert))
        if not ca_path.is_file():
            raise ValueError(f"MCP CA certificate not found: {ca_path}")
        return ssl.create_default_context(cafile=str(ca_path))

    async def list_tools(self, server_name: str) -> dict[str, Any]:
        server = self._server(server_name)
        async with httpx.AsyncClient(
            headers=self._headers(server),
            verify=self._tls_verify(server),
            follow_redirects=True,
            timeout=httpx.Timeout(30.0, read=300.0),
        ) as http_client:
            async with streamable_http_client(
                server["url"], http_client=http_client
            ) as (read_stream, write_stream, _):
                async with ClientSession(read_stream, write_stream) as session:
                    await session.initialize()
                    result = await session.list_tools()
                    data = result.model_dump(mode="json")
                    if "*" in server.get("allowed_tools", []):
                        return data
                    data["tools"] = [
                        tool
                        for tool in data.get("tools", [])
                        if self._tool_is_allowed(
                            server, str(tool.get("name", ""))
                        )
                    ]
                    return data

    async def call(
        self, server_name: str, tool_name: str, arguments: dict[str, Any]
    ) -> dict[str, Any]:
        server = self._server(server_name)
        if not self._tool_is_allowed(server, tool_name):
            raise ValueError("MCP tool is not allowlisted")

        async with httpx.AsyncClient(
            headers=self._headers(server),
            verify=self._tls_verify(server),
            follow_redirects=True,
            timeout=httpx.Timeout(30.0, read=300.0),
        ) as http_client:
            async with streamable_http_client(
                server["url"], http_client=http_client
            ) as (read_stream, write_stream, _):
                async with ClientSession(read_stream, write_stream) as session:
                    await session.initialize()
                    result = await session.call_tool(tool_name, arguments=arguments)
                    return result.model_dump(mode="json")
