# Tool Inventory

| Tool | Integration | Initial automation |
|---|---|---|
| CALDERA | REST API v2 | Read/report automatic; launch approved |
| ExtraHop | MCP Streamable HTTP | Read-only automatic |
| CrowdStrike | MCP Streamable HTTP | Read-only automatic |
| NetExec | BAS command adapter | Scoped discovery automatic |
| Certipy | BAS command adapter | Authenticated enumeration approved |
| BloodHound | REST API v2 signed token | Read-only Cypher automatic |
| Infection Monkey | Product API | Planned after API/version capture |
| Mythic | GraphQL/API token | Planned; tasking requires approval |
| GoPhish | REST API | Planned; campaign launch requires approval |
| Tuoni | REST API | Planned; C2 tasking requires approval |
| Generic Bash | BAS bubblewrap adapter | Approved; declared scoped targets |
| Impacket | Typed adapters or approved shell | Per-command approval policy |
| Responder | Managed service adapter | Planned; interface and duration approval |
| Sliver | Multiplayer/custom client | Planned; C2 tasking approval |
| Evil-WinRM | Session adapter | Planned; remote execution approval |

Before integration, rotate every credential previously stored in plaintext. Add
only new secrets to the executor's secret store or a dedicated vault.
