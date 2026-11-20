# Testing

## Local unit tests

```bash
python3 -m venv .venv-test
. .venv-test/bin/activate
python -m pip install --upgrade pip
pip install -e './security-agent[dev]' -e './bas-executor[dev]'

(cd security-agent && pytest -q)
(cd bas-executor && pytest -q)
python -m compileall -q security-agent/app bas-executor/executor
pip check
```

## Security checks

```bash
./scripts/check-no-secrets.sh
```

Confirm these files are untracked:

```bash
git status --short --ignored
```

- `security-agent/.env`
- `security-agent/models/*.gguf`
- `bas-executor/.env`
- `bas-executor/engagements/active.yaml`
- `bas-executor/secrets/credentials.yaml`
- Evidence artifacts

## BAS integration smoke tests

Use `bas-executor/scripts/signed_request.py`. Export the configured HMAC secret
only in the current admin shell.

Read-only:

```bash
python scripts/signed_request.py \
  --capability caldera.get_operation_report \
  --case-id report-test \
  --arguments '{"id":"OPERATION_ID","enable_agent_output":false}'
```

Approval test:

```bash
python scripts/signed_request.py \
  --capability shell.execute \
  --case-id shell-policy-test \
  --arguments '{"command":"nmap -sn 10.100.31.0/30","targets":["10.100.31.0/30"]}'
```

Expected status: `pending_approval`.

Out-of-scope test:

```bash
python scripts/signed_request.py \
  --capability shell.execute \
  --case-id shell-scope-test \
  --approved \
  --arguments '{"command":"curl http://8.8.8.8/","targets":["8.8.8.8"]}'
```

Expected result: HTTP 400 with an out-of-scope message.

## Deployment validation

AI VM:

```bash
./scripts/preflight.sh
cd security-agent
docker compose config
docker compose up -d --build
docker compose ps
curl http://127.0.0.1:8000/health
```

Web UI:

```bash
curl -kI https://10.100.31.3/
docker compose exec agent test -f /app/web/index.html
docker compose logs --tail=100 caddy
```

After trusting Caddy's public root CA on the operator workstation, this command
must succeed without `-k`:

```bash
curl -I https://10.100.31.3/
```

Verify login, case creation, conversation persistence, connector status, and
one read-only tool call. For an approval test, request a capability whose BAS
engagement category requires approval, review the exact arguments, then reject
it first. Confirm the rejection appears in the audit log.

BAS VM:

```bash
sudo systemctl status bas-executor
curl http://127.0.0.1:8010/health
sudo journalctl -u bas-executor -n 100 --no-pager
```

Do not mark an integration successful based only on HTTP health. Run one
read-only capability and inspect its artifact and audit record.
