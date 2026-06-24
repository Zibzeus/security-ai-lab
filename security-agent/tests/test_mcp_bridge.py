import ssl

import pytest

from app.mcp_bridge import MCPBridge


def test_mcp_wildcard_allows_any_exposed_tool() -> None:
    server = {"allowed_tools": ["*"]}
    assert MCPBridge._tool_is_allowed(server, "any.server.tool")


def test_mcp_explicit_allowlist_still_supported() -> None:
    server = {"allowed_tools": ["read_only_tool"]}
    assert MCPBridge._tool_is_allowed(server, "read_only_tool")
    assert not MCPBridge._tool_is_allowed(server, "write_tool")


def test_mcp_uses_system_trust_store_by_default() -> None:
    assert MCPBridge._tls_verify({}) is True


def test_mcp_rejects_missing_custom_ca(tmp_path) -> None:
    missing = tmp_path / "missing-ca.crt"
    with pytest.raises(ValueError, match="MCP CA certificate not found"):
        MCPBridge._tls_verify({"ca_cert": str(missing)})


def test_mcp_builds_context_from_custom_ca(tmp_path, monkeypatch) -> None:
    ca_file = tmp_path / "mcp-ca.crt"
    ca_file.write_text("test certificate", encoding="utf-8")
    expected = ssl.create_default_context()
    captured: dict[str, str] = {}

    def fake_create_default_context(*, cafile: str) -> ssl.SSLContext:
        captured["cafile"] = cafile
        return expected

    monkeypatch.setattr(ssl, "create_default_context", fake_create_default_context)

    assert MCPBridge._tls_verify({"ca_cert": str(ca_file)}) is expected
    assert captured["cafile"] == str(ca_file)
