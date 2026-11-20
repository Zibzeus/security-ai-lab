# Internal Security Agent

A small, local-first security agent for SOC triage, authorized red-team planning,
and governance analysis. It is designed for an Ubuntu VM with 8 vCPU, 12 GB RAM,
100 GB storage, and no GPU.

## Architecture

- `llama.cpp` serves one quantized local model.
- FastAPI provides the agent API.
- SQLite FTS5 stores approved internal knowledge and audit events.
- A deterministic policy engine mediates every tool request.
- SOC, red-team, and GRC profiles share the model but use separate instructions
  and permissions.
- Built-in MVP tools do not generate network traffic.

The MVP does not autonomously exploit, contain, block, or modify any endpoint.

The extended design uses a separate `bas-executor` service on the BAS VM. The
agent normally sends typed capability requests. An approved `shell.execute`
request may contain Bash text, but execution remains scoped and sandboxed on
the BAS VM.

## Recommended model

Start with the official `Qwen/Qwen3-4B-GGUF` model using
`Qwen3-4B-Q4_K_M.gguf`. Start with a 4096-token context on the 12 GB VM.

Place it under `models/`. Verify its publisher, license, hash, and provenance
before use.

## Start

```bash
cd security-agent
cp .env.example .env
openssl rand -hex 32
# Generate four independent values for API_KEY, APPROVAL_KEY,
# BAS_EXECUTOR_SECRET, and WEB_SESSION_SECRET.
docker compose build agent
docker compose run --rm --no-deps \
  --entrypoint python agent \
  /app/scripts/hash_web_password.py
# Put the resulting scrypt hash in WEB_PASSWORD_HASH using single quotes, then:
docker compose up -d
curl http://127.0.0.1:8000/health
```

## Web operations console

The lightweight Web UI provides authenticated SOC, Red Team, and GRC cases,
persistent conversation history, evidence, tool results, exact-action approval,
connector status, and audit history.

It is exposed through Caddy at:

```text
https://10.100.31.3/
```

The Agent API remains bound to localhost. Configure `WEB_USERNAME`,
`WEB_PASSWORD_HASH`, and `WEB_SESSION_SECRET` before startup. See
`../docs/WEB_UI_DEPLOYMENT_ID.md` for the complete deployment and CA trust
procedure.

Index approved knowledge:

```bash
curl -X POST http://127.0.0.1:8000/v1/knowledge/reindex \
  -H "X-API-Key: YOUR_KEY"
```

The reindex endpoint supports `.md`, `.txt`, and `.pdf`. PDF citations include
page and chunk numbers. Place runtime-only documents in `rag-sources/`; that
directory is mounted read-only and ignored by Git. See
`../docs/RAG_SOURCES_ID.md`.

Run a SOC investigation:

```bash
curl -X POST http://127.0.0.1:8000/v1/investigate \
  -H "Content-Type: application/json" \
  -H "X-API-Key: YOUR_KEY" \
  -d '{
    "profile": "soc",
    "objective": "Triage repeated Kerberos failures from 10.100.31.142",
    "evidence": ["12 failures in 5 minutes", "destination is the domain controller"]
  }'
```

## Resource budget

| Component | RAM target | CPU |
|---|---:|---:|
| 4B GGUF Q4 model and KV cache | 4-7 GB | 6 |
| Agent API, SQLite, OS headroom | 2-3 GB | 2 |

Actual use depends heavily on context length, quantization, and prompt size.

## Safety model

| Tool risk | Default |
|---|---|
| Read-only enrichment | Automatic |
| Security simulation | Dry-run |
| State-changing action | Human approval |
| Destructive action | Denied |

Targets passed to tools must be IP addresses inside `LAB_CIDRS`. Add real
connectors only with dedicated service accounts, least privilege, fixed upstream
URLs, strict request schemas, timeouts, and complete response logging.

## Next integrations

1. ExtraHop read-only detections, records, and device context.
2. CrowdStrike read-only host and detection enrichment.
3. Wazuh alert retrieval.
4. MITRE ATT&CK STIX ingestion.
5. A separate approval service for FortiGate or EDR containment.

Do not give the LLM unrestricted HTTP, unrestricted MCP, SSH credentials, or
database credentials. Generic shell is permitted only through the approved
`shell.execute` BAS capability and bubblewrap sandbox.

## Skills and BAS executor

Built-in skills are under `skills/`. A small manifest is used for discovery and
the full `SKILL.md` is loaded only when selected. Current skills cover CALDERA
operations, Active Directory assessment, and purple-team validation through
ExtraHop and CrowdStrike MCP.

Deploy the sibling `bas-executor` project on the BAS VM. Copy
`engagements/active.example.yaml` to `engagements/active.yaml`, adjust the scope,
and use the same `BAS_EXECUTOR_SECRET` on both services.
