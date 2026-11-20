import ipaddress
import hashlib
import hmac
import json
import secrets
import time
from abc import ABC, abstractmethod
from typing import Any

import httpx

from app.config import get_settings
from app.mcp_bridge import MCPBridge
from app.schemas import Risk


class Tool(ABC):
    name: str
    description: str
    risk: Risk

    @abstractmethod
    async def run(self, arguments: dict[str, Any], dry_run: bool) -> dict[str, Any]:
        raise NotImplementedError


class InspectTarget(Tool):
    name = "inspect_target"
    description = "Validate and describe a lab IP without sending traffic."
    risk = Risk.READ

    async def run(self, arguments: dict[str, Any], dry_run: bool) -> dict[str, Any]:
        address = ipaddress.ip_address(str(arguments.get("target", "")))
        return {
            "target": str(address),
            "version": address.version,
            "private": address.is_private,
            "global": address.is_global,
        }


class SimulateSecurityTest(Tool):
    name = "simulate_security_test"
    description = "Create a dry-run record for an authorized lab security test."
    risk = Risk.SIMULATE

    async def run(self, arguments: dict[str, Any], dry_run: bool) -> dict[str, Any]:
        return {
            "dry_run": True,
            "target": arguments.get("target"),
            "technique": arguments.get("technique"),
            "command_executed": False,
            "note": "No packet, process, or command was sent to the target.",
        }


class IsolateAsset(Tool):
    name = "isolate_asset"
    description = "Placeholder for EDR or firewall containment."
    risk = Risk.WRITE

    async def run(self, arguments: dict[str, Any], dry_run: bool) -> dict[str, Any]:
        return {
            "dry_run": dry_run,
            "target": arguments.get("target"),
            "executed": False,
            "note": "Connector is intentionally disabled in the MVP.",
        }


class BASExecute(Tool):
    name = "bas_execute"
    description = (
        "Run one allowlisted BAS capability. Active scanning is scoped automatically; "
        "higher-risk capabilities require explicit user approval."
    )
    risk = Risk.ACTIVE

    async def run(self, arguments: dict[str, Any], dry_run: bool) -> dict[str, Any]:
        settings = get_settings()
        body = json.dumps(arguments, sort_keys=True, separators=(",", ":")).encode()
        timestamp = str(int(time.time()))
        nonce = secrets.token_hex(16)
        signature = hmac.new(
            settings.bas_executor_secret.encode(),
            timestamp.encode() + b"." + nonce.encode() + b"." + body,
            hashlib.sha256,
        ).hexdigest()
        headers = {
            "X-BAS-Timestamp": timestamp,
            "X-BAS-Nonce": nonce,
            "X-BAS-Signature": signature,
            "Content-Type": "application/json",
        }
        async with httpx.AsyncClient(timeout=180) as client:
            response = await client.post(
                f"{settings.bas_executor_url.rstrip('/')}/v1/execute",
                content=body,
                headers=headers,
            )
            response.raise_for_status()
            return response.json()


class MCPQuery(Tool):
    name = "mcp_query"
    description = (
        "Call a tool exposed by a configured MCP server. Server-side credentials and "
        "the local wildcard/allowlist configuration still apply."
    )
    risk = Risk.READ

    async def run(self, arguments: dict[str, Any], dry_run: bool) -> dict[str, Any]:
        if not arguments.get("server"):
            raise ValueError(
                "mcp_query requires arguments.server, for example 'extrahop' or 'crowdstrike'"
            )
        if not arguments.get("tool"):
            raise ValueError("mcp_query requires arguments.tool with an exact MCP tool name")
        settings = get_settings()
        networks = [
            ipaddress.ip_network(item.strip())
            for item in settings.lab_cidrs.split(",")
            if item.strip()
        ]
        for key, value in dict(arguments.get("arguments", {})).items():
            if key.lower() not in {"ip", "target", "source_ip", "destination_ip"}:
                continue
            values = value if isinstance(value, list) else [value]
            for item in values:
                try:
                    address = ipaddress.ip_address(str(item))
                except ValueError:
                    continue
                if not any(address in network for network in networks):
                    raise ValueError("MCP query IP is outside configured lab CIDRs")
        bridge = MCPBridge(settings.mcp_config_file)
        return await bridge.call(
            server_name=str(arguments["server"]),
            tool_name=str(arguments["tool"]),
            arguments=dict(arguments.get("arguments", {})),
        )


class MCPListTools(Tool):
    name = "mcp_list_tools"
    description = "Discover tools exposed by one configured MCP server."
    risk = Risk.READ

    async def run(self, arguments: dict[str, Any], dry_run: bool) -> dict[str, Any]:
        if not arguments.get("server"):
            raise ValueError(
                "mcp_list_tools requires arguments.server, for example 'extrahop' or 'crowdstrike'"
            )
        bridge = MCPBridge(get_settings().mcp_config_file)
        return await bridge.list_tools(str(arguments["server"]))


TOOLS: dict[str, Tool] = {
    tool.name: tool
    for tool in [
        InspectTarget(),
        SimulateSecurityTest(),
        IsolateAsset(),
        BASExecute(),
        MCPListTools(),
        MCPQuery(),
    ]
}


TOOL_ARGUMENT_SCHEMAS: dict[str, dict[str, Any]] = {
    "inspect_target": {
        "required": ["target"],
        "example": {"target": "10.100.31.10"},
    },
    "simulate_security_test": {
        "required": ["target", "technique"],
        "example": {"target": "10.100.31.10", "technique": "T1046"},
    },
    "isolate_asset": {
        "required": ["target"],
        "example": {"target": "10.100.31.10"},
    },
    "bas_execute": {
        "required": ["capability", "arguments"],
        "example": {
            "capability": "nxc.smb_discover",
            "arguments": {"targets": ["10.100.31.0/24"]},
        },
    },
    "mcp_list_tools": {
        "required": ["server"],
        "allowed_servers": ["extrahop", "crowdstrike"],
        "example": {"server": "extrahop"},
    },
    "mcp_query": {
        "required": ["server", "tool", "arguments"],
        "allowed_servers": ["extrahop", "crowdstrike"],
        "example": {
            "server": "extrahop",
            "tool": "exact_tool_name_from_mcp_list_tools",
            "arguments": {"ip": "10.100.31.10"},
        },
    },
}


def tool_catalog() -> list[dict[str, Any]]:
    return [
        {
            "name": tool.name,
            "description": tool.description,
            "risk": tool.risk.value,
            "argument_schema": TOOL_ARGUMENT_SCHEMAS.get(tool.name, {}),
        }
        for tool in TOOLS.values()
    ]
