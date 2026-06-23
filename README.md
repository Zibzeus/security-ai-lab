# Security AI Lab

Local-first AI security platform for:

- SOC triage and investigation
- CALDERA adversary-emulation operations
- Active Directory assessment
- Purple-team validation using ExtraHop and CrowdStrike through MCP
- Security governance and evidence-based reporting

The project uses two separate trust zones:

| Component | Location | Responsibility |
|---|---|---|
| `security-agent` | AI VM | LLM inference, skills, RAG, policy, MCP |
| `bas-executor` | BAS VM | Scoped execution of registered capabilities |

Start with [docs/GETTING_STARTED_ID.md](docs/GETTING_STARTED_ID.md).
Deploy the authenticated HTTPS console with
[docs/WEB_UI_DEPLOYMENT_ID.md](docs/WEB_UI_DEPLOYMENT_ID.md).
Manage production knowledge sources with
[docs/RAG_SOURCES_ID.md](docs/RAG_SOURCES_ID.md).

## Implemented integrations

- CALDERA list, launch, operation detail, report, and event-log retrieval.
- BloodHound read-only Cypher queries using signed API-token authentication.
- NetExec and Certipy typed adapters.
- Generic Bash execution inside a bubblewrap filesystem sandbox.
- ExtraHop and CrowdStrike read-only MCP bridge.

Active scanning is automatic only inside the active engagement. Authenticated
enumeration, CALDERA launch, arbitrary shell/remote execution, credential
access, C2 tasking, and phishing require a separate approval key.

## Important

This project is intended only for systems you own or are explicitly authorized
to test. Model weights, credentials, active engagement files, and evidence are
excluded from Git.
