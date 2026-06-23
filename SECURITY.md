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

Rotate any credential that has previously appeared in chat, plaintext notes, Git,
logs, screenshots, or command history.

## Reporting

Do not open a public issue containing a vulnerability, credential, internal host,
or lab topology. Report it privately to the repository owner.
