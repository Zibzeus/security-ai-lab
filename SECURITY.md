# Security

## Never Commit

- `.env`
- API keys, passwords, cookies, or tokens
- Model files (`*.gguf`)
- `engagements/active.yaml`
- `secrets/credentials.yaml`
- Raw exercise artifacts
- Customer or production telemetry

## Enforcement boundaries

- The AI API key is not an approval credential. Approved capabilities require a
  separate `X-Approval-Key`.
- BAS categories not explicitly listed in the active engagement are denied.
- A denied category cannot be enabled by setting `approved=true`.
- Generic shell execution requires approval, declared targets, active
  engagement scope, and bubblewrap. It fails closed when bubblewrap is missing.
- The BAS VM egress firewall is the authoritative network boundary. Static
  command inspection is defense in depth, not a replacement for firewall rules.
- Never add `/opt/bas-executor`, its parent, or the credential directory to
  `SHELL_READONLY_BINDS`.
- The Web UI is exposed only through HTTPS. Keep the Agent API bound to
  `127.0.0.1:8000` and do not publish it directly to the LAN.
- Web approvals require both an authenticated Web session and the separate
  `APPROVAL_KEY`, then replay only the exact pending capability and arguments
  stored in SQLite. A browser cannot replace them with a different command.
- Web sessions use an HttpOnly, Secure, SameSite=Strict cookie plus a separate
  CSRF token. Use a unique password and rotate `WEB_SESSION_SECRET` if session
  material is suspected to be exposed.
- Caddy's internal CA private key lives in the `caddy-data` Docker volume.
  Never commit, share, or copy that private key. Only distribute the public
  root certificate to authorized operator workstations.
- Conversation history and submitted evidence are stored in the Agent SQLite
  volume. Treat backups as sensitive security evidence.
- Runtime RAG documents under `security-agent/rag-sources/` are untracked and
  may contain proprietary material. Do not commit source documents, extracted
  text, or the SQLite index.
- Only ingest documents with clear authorization and provenance. A public
  repository containing third-party books is not proof of redistribution
  rights.

Rotate any credential that has previously appeared in chat, plaintext notes, Git,
logs, screenshots, or command history.

## Reporting

Do not open a public issue containing a vulnerability, credential, internal host,
or lab topology. Report it privately to the repository owner.
