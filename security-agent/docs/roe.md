# Lab Rules of Engagement

## Authorization

This environment is a privately owned cyber range. Testing is authorized only
against assets explicitly listed in the active engagement file.

## Automatically Permitted

- Read-only API and MCP queries.
- Service and protocol discovery inside allowed CIDRs.
- Non-destructive SMB, LDAP, Kerberos, HTTP, and DNS enumeration.
- Retrieval of existing CALDERA operations and reports.

## Approval Required

- Launching a CALDERA operation.
- Authenticated enumeration using lab credentials.
- Remote command execution or lateral movement.
- Generic `shell.execute`, even when used only for discovery.
- Credential access, relay, poisoning, C2 tasking, payload generation, or phishing.

## Prohibited

- Targets outside the allowlist.
- Denial of service, destructive changes, ransomware encryption, log deletion,
  persistence beyond the exercise, or uncontrolled propagation.
- Internet targets unless separately and explicitly authorized.

## Stop Conditions

Stop immediately when a target is outside scope, a production dependency appears,
resource exhaustion is observed, unexpected data is accessed, or the kill switch
is enabled.
