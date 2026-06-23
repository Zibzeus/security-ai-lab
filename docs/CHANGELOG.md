# Changelog

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
