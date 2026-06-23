# BAS Shell Execution

Use `bas_execute` with capability `shell.execute` only when a typed capability
cannot perform the authorized task.

Required arguments:

- `command`: the exact Bash command.
- `targets`: every intended IP address or hostname.
- `timeout`: optional value from 1 to 900 seconds.

`shell.execute` always requires explicit capability approval. The BAS executor
runs it inside a bubblewrap filesystem sandbox and validates declared targets
against the active engagement. The network firewall on the BAS VM remains the
authoritative egress boundary.

Never hide targets through encoding, environment expansion, DNS indirection, or
downloaded scripts. Never place credentials directly in the command. Prefer a
typed capability whenever credentials are required.
