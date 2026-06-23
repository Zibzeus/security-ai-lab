# BAS Executor

Install this service on the BAS VM. It exposes structured capabilities to the
security agent. Typed adapters use `create_subprocess_exec`. The optional
`shell.execute` capability runs Bash inside a bubblewrap filesystem sandbox.

## Bootstrap

```bash
sudo apt install -y bubblewrap python3-venv
sudo useradd --system --home /opt/bas-executor --shell /usr/sbin/nologin bas-agent
sudo install -d -o root -g bas-agent -m 0750 /opt/bas-executor
sudo install -d -o bas-agent -g bas-agent -m 0700 /var/lib/bas-executor/artifacts
python3 -m venv /opt/bas-executor/.venv
/opt/bas-executor/.venv/bin/pip install .
cp engagements/active.example.yaml engagements/active.yaml
cp secrets/credentials.example.yaml secrets/credentials.yaml
chmod 600 .env secrets/credentials.yaml
```

Restrict port 8010 to the AI VM with a host firewall. Add WireGuard or an mTLS
reverse proxy before using it outside a private lab network. Never expose this
service directly to the internet.

## Capability policy

- `read_only` and `active_scan` are automatic when the engagement is active.
- Authenticated enumeration and CALDERA launch require explicit approval.
- `shell.execute` supports arbitrary Bash syntax but always requires approval,
  declared scoped targets, and a working bubblewrap sandbox.
- Add new tools as typed command builders in `executor/registry.py`.

The shell sandbox intentionally cannot see `/opt/bas-executor`, `.env`, or the
credential store. Add only exact tool installation roots to
`SHELL_READONLY_BINDS`.
