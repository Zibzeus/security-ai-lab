from datetime import UTC, datetime
from pathlib import Path

import pytest

from executor.runtime import (
    bloodhound_signature_headers,
    run_bloodhound,
    run_caldera,
    run_request,
    sanitized_audit_arguments,
    validate_read_only_cypher,
    validate_shell_scope,
)
from executor.config import Settings
from executor.models import ExecutionRequest
from executor.registry import CAPABILITIES, Capability
from executor.scope import Engagement


ENGAGEMENT = Path(__file__).parents[1] / "engagements" / "active.example.yaml"


def test_read_only_cypher_validation() -> None:
    validate_read_only_cypher("MATCH (n:Computer) RETURN n LIMIT 10")
    with pytest.raises(ValueError):
        validate_read_only_cypher("MATCH (n) DELETE n")
    with pytest.raises(ValueError):
        validate_read_only_cypher("MATCH (n) RETURN n; MATCH (m) RETURN m")


def test_shell_requires_declared_scoped_targets() -> None:
    engagement = Engagement.load(ENGAGEMENT)
    validate_shell_scope(
        "nmap -sV 10.100.31.20",
        ["10.100.31.20"],
        engagement,
    )
    with pytest.raises(ValueError):
        validate_shell_scope("id", [], engagement)
    with pytest.raises(ValueError):
        validate_shell_scope(
            "curl http://8.8.8.8/",
            ["10.100.31.20"],
            engagement,
        )


def test_bloodhound_signature_headers_are_stable() -> None:
    headers = bloodhound_signature_headers(
        "POST",
        "/api/v2/graphs/cypher",
        b'{"query":"MATCH (n) RETURN n"}',
        "00000000-0000-0000-0000-000000000001",
        "token-key",
        datetime(2026, 6, 23, 10, 20, 30, tzinfo=UTC),
    )
    assert headers["Authorization"].startswith("bhesignature ")
    assert headers["RequestDate"] == "2026-06-23T10:20:30Z"
    assert headers["Signature"] == "HJPLJSVqn+MfbCka4N6NYp0Uy45MUp9lzCDV/Ap4VEA="


def test_audit_redacts_secrets_and_hashes_shell() -> None:
    sanitized = sanitized_audit_arguments(
        {"command": "echo test", "api_token": "secret", "targets": ["10.0.0.1"]}
    )
    assert "command" not in sanitized
    assert sanitized["command_length"] == 9
    assert sanitized["api_token"] == "[REDACTED]"


@pytest.mark.asyncio
async def test_caldera_report_retrieval_uses_official_v2_route(
    monkeypatch, tmp_path
) -> None:
    captured = {}

    class Response:
        def raise_for_status(self) -> None:
            return None

        def json(self):
            return {"name": "operation-report"}

    class Client:
        def __init__(self, timeout):
            captured["timeout"] = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def request(self, method, url, headers, json):
            captured.update(
                method=method, url=url, headers=headers, payload=json
            )
            return Response()

    monkeypatch.setattr("executor.runtime.httpx.AsyncClient", Client)
    settings = Settings(
        executor_secret="x" * 32,
        caldera_url="http://caldera.local:8888",
        caldera_api_key="unit" * 4,
    )
    engagement = Engagement.load(ENGAGEMENT)
    result = await run_caldera(
        CAPABILITIES["caldera.get_operation_report"],
        {"id": "operation-123", "enable_agent_output": True},
        settings,
        tmp_path,
        engagement,
    )
    assert result.status == "success"
    assert captured["method"] == "POST"
    assert captured["url"].endswith(
        "/api/v2/operations/operation-123/report"
    )
    assert captured["payload"] == {"enable_agent_output": True}


@pytest.mark.asyncio
async def test_caldera_launch_builds_current_nested_payload(
    monkeypatch, tmp_path
) -> None:
    captured = {}

    class Response:
        def raise_for_status(self) -> None:
            return None

        def json(self):
            return {"id": "operation-123"}

    class Client:
        def __init__(self, timeout):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def request(self, method, url, headers, json):
            captured.update(method=method, url=url, payload=json)
            return Response()

    monkeypatch.setattr("executor.runtime.httpx.AsyncClient", Client)
    settings = Settings(
        executor_secret="x" * 32,
        caldera_url="http://caldera.local:8888",
        caldera_api_key="unit" * 4,
    )
    engagement = Engagement.load(ENGAGEMENT)
    adversary = engagement.caldera_adversaries[0]
    group = engagement.caldera_groups[0]
    await run_caldera(
        CAPABILITIES["caldera.launch_operation"],
        {
            "name": "lab-operation",
            "adversary": adversary,
            "group": group,
            "planner": "atomic",
            "source": "basic",
        },
        settings,
        tmp_path,
        engagement,
    )
    assert captured["payload"]["adversary"] == {"adversary_id": adversary}
    assert captured["payload"]["planner"] == {"id": "atomic"}
    assert captured["payload"]["source"] == {"id": "basic"}


@pytest.mark.asyncio
async def test_bloodhound_adapter_posts_signed_read_only_query(
    monkeypatch, tmp_path
) -> None:
    captured = {}

    class Response:
        content = b'{"data":{"nodes":{},"edges":[]}}'

        def raise_for_status(self) -> None:
            return None

    class Client:
        def __init__(self, timeout):
            captured["timeout"] = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def post(self, url, headers, content):
            captured.update(url=url, headers=headers, content=content)
            return Response()

    monkeypatch.setattr("executor.runtime.httpx.AsyncClient", Client)
    settings = Settings(
        executor_secret="x" * 32,
        bloodhound_url="http://bloodhound.local:8080",
        bloodhound_token_id="00000000-0000-0000-0000-000000000001",
        bloodhound_token_key="bloodhound-key",
    )
    result = await run_bloodhound(
        CAPABILITIES["bloodhound.cypher_query"],
        {
            "query": "MATCH (n:Computer) RETURN n LIMIT 5",
            "include_properties": True,
        },
        settings,
        tmp_path,
    )
    assert result.status == "success"
    assert captured["url"].endswith("/api/v2/graphs/cypher")
    assert captured["headers"]["Authorization"].startswith("bhesignature ")
    assert b"MATCH (n:Computer)" in captured["content"]


@pytest.mark.asyncio
async def test_denied_category_cannot_be_bypassed_by_approval(tmp_path) -> None:
    capability = Capability(
        "test.destructive",
        "destructive",
        10,
        command=lambda arguments, secrets, output: ["false"],
    )
    CAPABILITIES[capability.name] = capability
    try:
        settings = Settings(
            executor_secret="x" * 32,
            engagement_file=ENGAGEMENT,
            artifact_dir=tmp_path,
        )
        result = await run_request(
            ExecutionRequest(
                capability=capability.name,
                arguments={},
                case_id="case-denied",
                approved=True,
            ),
            settings,
        )
        assert result.status == "denied"
    finally:
        CAPABILITIES.pop(capability.name, None)
