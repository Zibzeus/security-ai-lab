from app.mcp_bridge import MCPBridge


def test_mcp_wildcard_allows_any_exposed_tool() -> None:
    server = {"allowed_tools": ["*"]}
    assert MCPBridge._tool_is_allowed(server, "any.server.tool")


def test_mcp_explicit_allowlist_still_supported() -> None:
    server = {"allowed_tools": ["read_only_tool"]}
    assert MCPBridge._tool_is_allowed(server, "read_only_tool")
    assert not MCPBridge._tool_is_allowed(server, "write_tool")
