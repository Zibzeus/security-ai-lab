import asyncio
import base64
import hashlib
import hmac
import json
import os
import re
import secrets
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx
import yaml

from executor.config import Settings
from executor.models import ExecutionRequest, ExecutionResponse
from executor.registry import CAPABILITIES, Capability
from executor.scope import Engagement, validate_targets


SAFE_ID = re.compile(r"^[A-Za-z0-9_.:-]{1,128}$")
IPV4_LITERAL = re.compile(r"(?<![\w.])(?:\d{1,3}\.){3}\d{1,3}(?![\w.])")
URL_LITERAL = re.compile(r"https?://[^\s'\"<>]+", re.IGNORECASE)
CYPHER_MUTATION = re.compile(
    r"\b(CREATE|MERGE|DELETE|DETACH|SET|REMOVE|DROP|LOAD\s+CSV|FOREACH|CALL)\b",
    re.IGNORECASE,
)


def load_secrets(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return {str(key): str(value) for key, value in raw.items()}


def clean_case_id(value: str) -> str:
    if not SAFE_ID.fullmatch(value):
        raise ValueError("Invalid case ID")
    return value


def append_audit(case_dir: Path, detail: dict[str, Any]) -> None:
    event = {
        "timestamp": datetime.now(UTC).isoformat(),
        **detail,
    }
    path = case_dir / "audit.jsonl"
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(event, ensure_ascii=True, default=str) + "\n")
    path.chmod(0o600)


def write_private_bytes(path: Path, content: bytes) -> None:
    path.write_bytes(content)
    path.chmod(0o600)


def write_private_text(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(0o600)


def sanitized_audit_arguments(arguments: dict[str, Any]) -> dict[str, Any]:
    sensitive_fragments = {"password", "token", "secret", "key"}
    result: dict[str, Any] = {}
    for key, value in arguments.items():
        lowered = key.lower()
        if any(fragment in lowered for fragment in sensitive_fragments):
            result[key] = "[REDACTED]"
        elif key == "command":
            command = str(value)
            result["command_sha256"] = hashlib.sha256(command.encode()).hexdigest()
            result["command_length"] = len(command)
        else:
            result[key] = value
    return result


def validate_read_only_cypher(query: str) -> None:
    if not query.strip():
        raise ValueError("BloodHound Cypher query is required")
    if len(query) > 8_000:
        raise ValueError("BloodHound Cypher query is too long")
    if ";" in query:
        raise ValueError("Multiple Cypher statements are not permitted")
    if CYPHER_MUTATION.search(query):
        raise ValueError("Only read-only BloodHound Cypher queries are permitted")


def validate_shell_scope(
    command: str, declared_targets: list[str], engagement: Engagement
) -> None:
    if not declared_targets:
        raise ValueError("shell.execute requires a non-empty targets list")
    for target in declared_targets:
        engagement.validate_target(target)
    for value in IPV4_LITERAL.findall(command):
        engagement.validate_target(value)
    for value in URL_LITERAL.findall(command):
        hostname = urlparse(value).hostname
        if hostname:
            engagement.validate_target(hostname)


def bloodhound_signature_headers(
    method: str,
    path: str,
    body: bytes,
    token_id: str,
    token_key: str,
    request_time: datetime | None = None,
) -> dict[str, str]:
    if not token_id or not token_key:
        raise ValueError("BloodHound token ID and key are required")
    timestamp = (request_time or datetime.now(UTC)).isoformat().replace("+00:00", "Z")
    operation_key = hmac.new(
        token_key.encode(), f"{method}{path}".encode(), hashlib.sha256
    ).digest()
    date_key = hmac.new(
        operation_key, timestamp[:13].encode(), hashlib.sha256
    ).digest()
    signature = hmac.new(date_key, body, hashlib.sha256).digest()
    return {
        "Authorization": f"bhesignature {token_id}",
        "RequestDate": timestamp,
        "Signature": base64.b64encode(signature).decode(),
        "Content-Type": "application/json",
    }


async def run_request(
    request: ExecutionRequest, settings: Settings
) -> ExecutionResponse:
    engagement = Engagement.load(settings.engagement_file)
    if not engagement.active:
        raise ValueError("No active engagement")
    capability = CAPABILITIES.get(request.capability)
    if not capability:
        raise ValueError("Unknown capability")
    validate_targets(engagement, request.arguments)
    case_root = settings.artifact_dir / clean_case_id(request.case_id)
    case_root.mkdir(parents=True, exist_ok=True, mode=0o700)
    case_root.chmod(0o700)
    run_id = (
        f"{datetime.now(UTC).strftime('%Y%m%dT%H%M%S%fZ')}-"
        f"{capability.name.replace('.', '_')}-{secrets.token_hex(4)}"
    )
    case_dir = case_root / run_id
    case_dir.mkdir(mode=0o700)
    category_action = engagement.category_action(capability.category)
    if category_action == "deny":
        result = ExecutionResponse(
            capability=capability.name,
            status="denied",
            artifact_dir=str(case_dir),
        )
    elif category_action == "approval" and not request.approved:
        result = ExecutionResponse(
            capability=capability.name,
            status="pending_approval",
            artifact_dir=str(case_dir),
        )
    elif capability.api_action == "shell_execute":
        result = await run_shell(
            capability, request.arguments, settings, case_dir, engagement
        )
    elif capability.api_action == "bloodhound_cypher_query":
        result = await run_bloodhound(
            capability, request.arguments, settings, case_dir
        )
    elif capability.api_action:
        result = await run_caldera(
            capability, request.arguments, settings, case_dir, engagement
        )
    else:
        result = await run_command(capability, request.arguments, settings, case_dir)
    append_audit(
        case_root,
        {
            "engagement_id": engagement.engagement_id,
            "capability": capability.name,
            "category": capability.category,
            "approved": request.approved,
            "policy_action": category_action,
            "arguments": sanitized_audit_arguments(request.arguments),
            "status": result.status,
            "exit_code": result.exit_code,
            "artifact_dir": result.artifact_dir,
        },
    )
    return result


async def run_command(
    capability: Capability,
    arguments: dict[str, Any],
    settings: Settings,
    case_dir: Path,
) -> ExecutionResponse:
    secrets = load_secrets(settings.credential_file)
    if capability.command is None:
        raise ValueError("Capability has no command")
    command = capability.command(arguments, secrets, str(case_dir))
    process = await asyncio.create_subprocess_exec(
        *command,
        cwd=case_dir,
        env={
            "PATH": os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin"),
            "HOME": str(case_dir),
            "LANG": "C.UTF-8",
            "LC_ALL": "C.UTF-8",
        },
        stdin=asyncio.subprocess.DEVNULL,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(
            process.communicate(), timeout=capability.timeout
        )
    except TimeoutError:
        process.kill()
        await process.wait()
        return ExecutionResponse(
            capability=capability.name,
            status="timeout",
            artifact_dir=str(case_dir),
        )
    limit = settings.max_output_bytes
    write_private_bytes(case_dir / "stdout.txt", stdout[:limit])
    write_private_bytes(case_dir / "stderr.txt", stderr[:limit])
    return ExecutionResponse(
        capability=capability.name,
        status="success" if process.returncode == 0 else "error",
        exit_code=process.returncode,
        stdout=stdout[:limit].decode(errors="replace"),
        stderr=stderr[:limit].decode(errors="replace"),
        artifact_dir=str(case_dir),
    )


async def run_caldera(
    capability: Capability,
    arguments: dict[str, Any],
    settings: Settings,
    case_dir: Path,
    engagement: Engagement,
) -> ExecutionResponse:
    paths = {
        "list_agents": ("GET", "/api/v2/agents"),
        "list_adversaries": ("GET", "/api/v2/adversaries"),
        "list_operations": ("GET", "/api/v2/operations"),
        "get_operation": ("GET", f"/api/v2/operations/{arguments.get('id', '')}"),
        "get_operation_report": (
            "POST",
            f"/api/v2/operations/{arguments.get('id', '')}/report",
        ),
        "get_operation_event_logs": (
            "POST",
            f"/api/v2/operations/{arguments.get('id', '')}/event-logs",
        ),
        "launch_operation": ("POST", "/api/v2/operations"),
    }
    if capability.api_action in {
        "get_operation",
        "get_operation_report",
        "get_operation_event_logs",
    }:
        operation_id = str(arguments.get("id", ""))
        if not SAFE_ID.fullmatch(operation_id):
            raise ValueError("Invalid CALDERA operation ID")
    method, path = paths[capability.api_action]
    payload = None
    if capability.api_action == "launch_operation":
        name = str(arguments.get("name", ""))
        adversary = str(arguments.get("adversary", ""))
        group = str(arguments.get("group", ""))
        if not name or not adversary:
            raise ValueError("Operation name and adversary are required")
        if adversary not in engagement.caldera_adversaries:
            raise ValueError("CALDERA adversary is not allowlisted")
        if group not in engagement.caldera_groups:
            raise ValueError("CALDERA group is not allowlisted")
        payload = {
            "name": name,
            "adversary": {"adversary_id": adversary},
            "planner": {"id": str(arguments.get("planner", "atomic"))},
            "source": {"id": str(arguments.get("source", "basic"))},
            "group": group,
            "autonomous": bool(arguments.get("autonomous", True)),
            "auto_close": bool(arguments.get("auto_close", False)),
        }
    elif capability.api_action in {
        "get_operation_report",
        "get_operation_event_logs",
    }:
        payload = {
            "enable_agent_output": bool(
                arguments.get("enable_agent_output", False)
            )
        }
    if not settings.caldera_api_key:
        raise ValueError("CALDERA_API_KEY is not configured")
    headers = {"KEY": settings.caldera_api_key}
    async with httpx.AsyncClient(timeout=capability.timeout) as client:
        response = await client.request(
            method,
            f"{settings.caldera_url.rstrip('/')}{path}",
            headers=headers,
            json=payload,
        )
        response.raise_for_status()
        data = response.json()
    artifact = case_dir / f"{capability.api_action}.json"
    write_private_text(artifact, json.dumps(data, indent=2))
    return ExecutionResponse(
        capability=capability.name,
        status="success",
        stdout=json.dumps(data)[: settings.max_output_bytes],
        artifact_dir=str(case_dir),
    )


async def run_bloodhound(
    capability: Capability,
    arguments: dict[str, Any],
    settings: Settings,
    case_dir: Path,
) -> ExecutionResponse:
    query = str(arguments.get("query", ""))
    validate_read_only_cypher(query)
    path = "/api/v2/graphs/cypher"
    payload = {
        "query": query,
        "include_properties": bool(arguments.get("include_properties", True)),
    }
    body = json.dumps(
        payload, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    headers = bloodhound_signature_headers(
        "POST",
        path,
        body,
        settings.bloodhound_token_id,
        settings.bloodhound_token_key,
    )
    async with httpx.AsyncClient(timeout=capability.timeout) as client:
        response = await client.post(
            f"{settings.bloodhound_url.rstrip('/')}{path}",
            headers=headers,
            content=body,
        )
        response.raise_for_status()
    limited = response.content[: settings.max_output_bytes]
    write_private_bytes(case_dir / "bloodhound.cypher.json", limited)
    return ExecutionResponse(
        capability=capability.name,
        status="success",
        stdout=limited.decode(errors="replace"),
        artifact_dir=str(case_dir),
    )


async def run_shell(
    capability: Capability,
    arguments: dict[str, Any],
    settings: Settings,
    case_dir: Path,
    engagement: Engagement,
) -> ExecutionResponse:
    command_text = str(arguments.get("command", ""))
    if not command_text.strip():
        raise ValueError("shell.execute requires a command")
    if len(command_text) > settings.max_shell_command_chars:
        raise ValueError("Shell command exceeds MAX_SHELL_COMMAND_CHARS")
    raw_targets = arguments.get("targets", [])
    targets = (
        [str(item) for item in raw_targets]
        if isinstance(raw_targets, list)
        else [str(raw_targets)]
    )
    validate_shell_scope(command_text, targets, engagement)
    if not settings.bubblewrap_path.is_file():
        raise ValueError("bubblewrap is required for shell.execute")
    if not settings.shell_path.is_file():
        raise ValueError("Configured shell path does not exist")

    sandbox_command = [
        str(settings.bubblewrap_path),
        "--die-with-parent",
        "--new-session",
        "--unshare-pid",
        "--unshare-ipc",
        "--unshare-uts",
        "--proc",
        "/proc",
        "--dev",
        "/dev",
        "--tmpfs",
        "/tmp",
        "--dir",
        "/home",
    ]
    for raw_path in settings.shell_readonly_binds.split(","):
        bind_path = raw_path.strip()
        if not bind_path:
            continue
        sandbox_command.extend(["--ro-bind-try", bind_path, bind_path])
    sandbox_command.extend(
        [
            "--bind",
            str(case_dir),
            "/work",
            "--chdir",
            "/work",
            "--setenv",
            "HOME",
            "/work",
            "--setenv",
            "PATH",
            "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
            "--",
            str(settings.shell_path),
            "--noprofile",
            "--norc",
            "-c",
            command_text,
        ]
    )
    timeout = min(
        max(int(arguments.get("timeout", capability.timeout)), 1),
        capability.timeout,
    )
    write_private_text(case_dir / "command.txt", command_text + "\n")
    write_private_text(
        case_dir / "command.sha256",
        hashlib.sha256(command_text.encode()).hexdigest() + "\n",
    )
    process = await asyncio.create_subprocess_exec(
        *sandbox_command,
        stdin=asyncio.subprocess.DEVNULL,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout)
    except TimeoutError:
        process.kill()
        await process.wait()
        return ExecutionResponse(
            capability=capability.name,
            status="timeout",
            artifact_dir=str(case_dir),
        )
    limit = settings.max_output_bytes
    write_private_bytes(case_dir / "stdout.txt", stdout[:limit])
    write_private_bytes(case_dir / "stderr.txt", stderr[:limit])
    return ExecutionResponse(
        capability=capability.name,
        status="success" if process.returncode == 0 else "error",
        exit_code=process.returncode,
        stdout=stdout[:limit].decode(errors="replace"),
        stderr=stderr[:limit].decode(errors="replace"),
        artifact_dir=str(case_dir),
    )
