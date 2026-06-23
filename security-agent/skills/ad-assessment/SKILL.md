# Active Directory Assessment

## Workflow

1. Confirm the active engagement, domain, domain controller, and target CIDRs.
2. Use `bas_execute` with `nxc.smb_discover` or `nxc.ldap_discover` for automatic
   scoped discovery.
3. Use `mcp_query` to check existing endpoint and network telemetry before
   authenticated activity.
4. Propose authenticated enumeration separately. `certipy.find` requires explicit
   capability approval and a `credential_ref`.
5. Use `bloodhound.cypher_query` for read-only BloodHound analysis. Query only
   the minimum graph required and prefer explicit `LIMIT` clauses.
6. Prioritize shortest paths to tier-zero assets and paths introduced by
   misconfiguration.
7. Report evidence, attack path, impact, ATT&CK mapping, detection visibility,
   and remediation.

Do not perform password spraying, credential dumping, remote execution, relay,
poisoning, persistence, or privilege escalation as part of the default workflow.
