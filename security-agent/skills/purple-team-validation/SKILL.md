# Purple-Team Validation

## Workflow

1. Define one hypothesis: technique, source, destination, expected endpoint
   telemetry, expected network telemetry, and observation window.
2. Record a UTC baseline using read-only `mcp_query` calls to ExtraHop and
   CrowdStrike.
3. Run the approved CALDERA operation or scoped BAS capability.
4. Query both MCP servers using the same entities and time window.
5. Classify each control as `detected`, `telemetry-only`, `not-detected`, or
   `not-observable`.
6. Distinguish product failure from missing sensor coverage, wrong query, clock
   skew, ingestion delay, or unsupported telemetry.
7. Produce a result using `docs/report-template.md`.

Never treat the absence of an alert as proof that no telemetry exists.
