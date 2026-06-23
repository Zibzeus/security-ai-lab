# Changelog

## 2026-06-23 - Security Agent container build

- Copied the Python `app` package before running `pip install .` in the image.
- Added a CI Docker build to catch container-only packaging failures.

## 2026-06-23 - 8 GB AI VM profile

- Made Compose CPU and memory limits configurable through `.env`.
- Set the default profile to Qwen3-4B Q4_K_M with context 2048, batch 64,
  three llama.cpp threads, and a 5.5 GB model-container limit.

## 2026-06-23 - Dynamic MCP and BAS discovery

- Added MCP wildcard mode while retaining server-side authentication.
- Added `mcp_list_tools` for runtime MCP discovery.
- Added `bas.list_capabilities` for BAS capability discovery.
- Kept arbitrary BAS binaries behind approved, scoped, sandboxed
  `shell.execute`.

## 2026-06-23 - CI secret-scan false positive

- Replaced literal CALDERA test credentials with generated unit-test-only values.
- Preserved secret scanning for tests and production code instead of excluding the
  test directory.

## 2026-06-23

- Added separate approval authentication.
- Added fail-closed runtime secret validation.
- Enforced automatic, approval, denied, and unknown engagement categories.
- Added bubblewrap-based generic shell execution.
- Added BloodHound signed read-only Cypher adapter.
- Added CALDERA operation report and event-log retrieval.
- Corrected CALDERA v2 launch payload.
- Added CIDR target validation and nested target validation.
- Added private, unique evidence directories.
- Fixed package discovery and SQLite connection lifecycle.
- Reduced default CPU-only inference context and batch size.
- Added detailed Indonesian installation and testing guides.
