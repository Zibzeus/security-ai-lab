# Two-VM Deployment

## Security Agent VM

- Ubuntu Server, 8 vCPU, 12 GB RAM, 100 GB storage.
- Run the 4B GGUF model, agent API, RAG database, and MCP client.
- Permit outbound traffic only to the BAS executor and approved MCP endpoints.
- Do not install offensive binaries on this VM.

## BAS VM

- Install `bas-executor` alongside the existing security tools.
- Bind Uvicorn to loopback and expose it through WireGuard or an mTLS reverse proxy.
- Run it as the dedicated `bas-agent` account.
- Allow that account to execute only the tool binaries required by registered
  capabilities.

## Trust Boundary

1. Agent signs the exact JSON request using HMAC-SHA256.
2. Executor rejects stale timestamps and replayed nonces.
3. Executor loads the active engagement from local disk.
4. Target and CALDERA allowlists are checked locally on the BAS VM.
5. Typed commands are built as argument arrays. Generic shell uses bubblewrap,
   cannot mount the executor credential directory, and always needs approval.
6. Raw output and an audit event are stored under the case directory.

Bind BAS Executor to its private lab IP or loopback behind WireGuard/mTLS.
Do not bind to every interface unless a host firewall allows port 8010 only
from the AI VM.

Use different secrets for the user-facing API, BAS executor signing, MCP servers,
CALDERA, and every product account.

## First Exercise

1. Rotate all credentials previously kept in `BAS.txt`.
2. Configure the engagement CIDRs, domain, CALDERA group, and adversary ID.
3. Configure actual ExtraHop and CrowdStrike MCP tool names in `connectors/mcp.yaml`.
4. Reindex the starter SOP, ROE, report template, and knowledge files.
5. Run `nxc.smb_discover` against one lab IP.
6. Verify the case artifacts and corresponding ExtraHop/CrowdStrike telemetry.
7. Only then approve a small CALDERA operation.
