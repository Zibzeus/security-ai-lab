# Panduan Instalasi Lengkap Security AI Lab

Panduan ini dimulai dari VM Ubuntu kosong sampai model, Security Agent, BAS
Executor, CALDERA report retrieval, BloodHound, MCP, dan generic shell siap
diuji.

## 1. Arsitektur

Gunakan dua VM terpisah:

```text
Operator
   |
   v
AI VM: Qwen3-4B + llama.cpp + Security Agent + RAG + MCP client
   |
   | HMAC-signed capability request
   v
BAS VM: policy enforcement + CALDERA/BloodHound/tools + artifacts
   |
   v
Engagement allowlist targets
```

Spesifikasi target AI VM:

```text
Ubuntu Server 24.04 LTS
8 vCPU
12 GB RAM
100 GB storage
Tanpa GPU
```

Profil minimum yang sudah disiapkan di Compose adalah 4 vCPU, 8 GB RAM, swap
4 GB, context 2048, batch 64, tiga thread llama.cpp, dan satu parallel slot.
Jangan menjalankan platform BAS berat pada AI VM minimum ini.

BAS VM harus terpisah dan memiliki tools security yang dibutuhkan.

## 2. Policy yang berlaku

Otomatis, jika target berada di engagement allowlist:

- Read-only CALDERA, BloodHound, ExtraHop, dan CrowdStrike query.
- Active service/protocol scanning.

Memerlukan approval terpisah:

- Authenticated enumeration.
- CALDERA operation launch.
- Generic shell dan remote execution.
- Credential access.
- C2 tasking.
- Phishing.

Selalu ditolak:

- Target di luar allowlist.
- Destructive action.
- Denial of service.
- Log deletion.
- Uncontrolled propagation.

`API_KEY` dan `APPROVAL_KEY` harus berbeda. Memiliki akses ke API agent tidak
berarti memiliki hak approval.

## 3. Siapkan repository GitHub

Gunakan repository private selama topology dan adapter masih berkembang.

Pada kedua VM:

```bash
sudo apt update
sudo apt install -y ca-certificates curl git jq python3 python3-venv
git clone https://github.com/Zibzeus/security-ai-lab.git
cd security-ai-lab
```

Jika URL repository berbeda, gunakan URL repository Anda. Jangan memasukkan PAT
ke URL clone.

## 4. Instal Docker pada AI VM

```bash
sudo apt remove -y docker.io docker-compose docker-compose-v2 docker-doc \
  podman-docker containerd runc || true
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
  -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc

echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "${UBUNTU_CODENAME:-$VERSION_CODENAME}") stable" |
  sudo tee /etc/apt/sources.list.d/docker.list >/dev/null

sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io \
  docker-buildx-plugin docker-compose-plugin
sudo systemctl enable --now docker
sudo docker run --rm hello-world
```

Opsional:

```bash
sudo usermod -aG docker "$USER"
exit
```

Login kembali agar group baru aktif.

## 5. Download model resmi

Model:

```text
Repository : Qwen/Qwen3-4B-GGUF
File       : Qwen3-4B-Q4_K_M.gguf
License    : Apache-2.0
```

Jalankan:

```bash
cd ~/security-ai-lab
chmod +x scripts/*.sh
./scripts/download-model.sh
```

Verifikasi:

```bash
ls -lh security-agent/models/
sha256sum -c security-agent/models/Qwen3-4B-Q4_K_M.gguf.sha256
```

Model dan checksum lokal di-ignore oleh Git.

## 6. Uji model secara terpisah

```bash
docker run --rm \
  -p 127.0.0.1:8080:8080 \
  -v "$PWD/security-agent/models:/models:ro" \
  ghcr.io/ggml-org/llama.cpp:server \
  -m /models/Qwen3-4B-Q4_K_M.gguf \
  --host 0.0.0.0 \
  --port 8080 \
  -c 4096 \
  -t 6 \
  -b 128 \
  --parallel 1 \
  --jinja
```

Terminal kedua:

```bash
curl http://127.0.0.1:8080/health

curl http://127.0.0.1:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "local-model",
    "messages": [
      {
        "role": "user",
        "content": "Return JSON only: {\"status\":\"ready\"} /no_think"
      }
    ],
    "temperature": 0.1
  }'
```

Hentikan test server dengan `Ctrl+C`.

## 7. Konfigurasi Security Agent

```bash
cd ~/security-ai-lab/security-agent
cp .env.example .env
openssl rand -hex 32
openssl rand -hex 32
openssl rand -hex 32
openssl rand -hex 32
```

Gunakan empat hasil berbeda:

```dotenv
API_KEY=<random-pertama>
APPROVAL_KEY=<random-kedua>
BAS_EXECUTOR_SECRET=<random-ketiga>
WEB_SESSION_SECRET=<random-keempat>
WEB_USERNAME=admin

LLM_BASE_URL=http://llama:8080/v1
LLM_MODEL=local-model
LLM_CONTEXT_SIZE=2048
LLM_BATCH_SIZE=64
LLM_DISABLE_THINKING=true
LLM_PLAN_MAX_TOKENS=350
LLM_REPORT_MAX_TOKENS=650
LLAMA_THREADS=3
LLAMA_MEMORY_LIMIT=5500m
LLAMA_CPUS=3
AGENT_MEMORY_LIMIT=768m
AGENT_CPUS=1

LAB_CIDRS=10.100.31.0/24,10.10.0.0/16
BAS_EXECUTOR_URL=http://<BAS_PRIVATE_IP>:8010
```

Build image Agent lalu buat password hash Web UI:

```bash
docker compose build agent
docker compose run --rm --no-deps \
  --entrypoint python agent \
  /app/scripts/hash_web_password.py
```

Tambahkan output `scrypt$...` ke `.env`:

```dotenv
WEB_PASSWORD_HASH=scrypt$...
WEB_SECURE_COOKIE=true
ENABLE_API_DOCS=false
```

Jika menulis nilai ini via shell, pakai single-quoted heredoc atau editor.
Jangan `echo "WEB_PASSWORD_HASH=scrypt$..."` karena `$` dapat di-expand oleh
shell sebelum masuk `.env`.

Gunakan permission ketat:

```bash
chmod 600 .env
```

Tes hash login sebelum membuka browser:

```bash
docker compose run --rm --no-deps \
  --entrypoint python agent \
  /app/scripts/verify_web_password.py
```

`APPROVAL_KEY` hanya diberikan kepada approver/operator yang berwenang. Password
Web UI tidak menggantikan approval key; eksekusi yang memerlukan approval tetap
meminta credential tersebut.

## 8. Konfigurasi MCP

Edit:

```bash
nano connectors/mcp.yaml
```

Sesuaikan URL dengan MCP server yang benar-benar aktif. Untuk topology lab ini:

```yaml
servers:
  extrahop:
    url: https://10.100.31.4:8325/mcp
    ca_cert: /app/local-certs/extrahop-mcp.crt
    allowed_tools:
      - "*"
  crowdstrike:
    url: http://10.100.31.4:8000/mcp
    allowed_tools:
      - "*"
```

Wildcard membuat `mcp_list_tools` dan `mcp_query` dapat memakai seluruh tool
yang diekspos server tersebut, tanpa daftar nama statis. Ini bukan bypass
otorisasi: permission akun/API token dan policy pada MCP server tetap berlaku.
Untuk server yang juga memiliki tool write/destructive, gunakan credential
read-only atau ganti wildcard dengan allowlist eksplisit.

## 9. Jalankan Security Agent

Dari root repository:

```bash
./scripts/preflight.sh
```

Lalu:

```bash
cd security-agent
docker compose pull
docker compose up -d --build
docker compose ps
docker compose logs --tail=100 llama
docker compose logs --tail=100 agent
docker compose logs --tail=100 caddy
```

Health:

```bash
curl http://127.0.0.1:8000/health
curl -kI https://10.100.31.3/
```

Untuk trust CA dan akses browser tanpa warning, ikuti
`docs/WEB_UI_DEPLOYMENT_ID.md`.

Index knowledge:

```bash
set -a
source .env
set +a

curl -X POST http://127.0.0.1:8000/v1/knowledge/reindex \
  -H "X-API-Key: ${API_KEY}"
```

## 10. Siapkan BAS VM

Install package dasar dan bubblewrap:

```bash
sudo apt update
sudo apt upgrade -y
sudo apt install -y python3 python3-venv git curl jq bubblewrap ufw
timedatectl
```

`bubblewrap` wajib untuk `shell.execute`.

Clone:

```bash
git clone https://github.com/Zibzeus/security-ai-lab.git
cd security-ai-lab/bas-executor
```

Create service user and directories:

```bash
sudo useradd --system \
  --home /opt/bas-executor \
  --shell /usr/sbin/nologin \
  bas-agent || true

sudo install -d -o root -g bas-agent -m 0750 /opt/bas-executor
sudo install -d -o bas-agent -g bas-agent -m 0700 \
  /var/lib/bas-executor/artifacts

sudo cp -a . /opt/bas-executor/
sudo chown -R root:bas-agent /opt/bas-executor
sudo python3 -m venv /opt/bas-executor/.venv
sudo /opt/bas-executor/.venv/bin/pip install /opt/bas-executor
```

Create runtime files:

```bash
sudo cp /opt/bas-executor/.env.example /opt/bas-executor/.env
sudo cp /opt/bas-executor/engagements/active.example.yaml \
  /opt/bas-executor/engagements/active.yaml
sudo cp /opt/bas-executor/secrets/credentials.example.yaml \
  /opt/bas-executor/secrets/credentials.yaml

sudo chown root:bas-agent \
  /opt/bas-executor/.env \
  /opt/bas-executor/engagements/active.yaml \
  /opt/bas-executor/secrets/credentials.yaml
sudo chmod 640 \
  /opt/bas-executor/.env \
  /opt/bas-executor/engagements/active.yaml \
  /opt/bas-executor/secrets/credentials.yaml
```

The source directory and secret files must not be readable by arbitrary shell
execution.

## 11. Konfigurasi BAS Executor

```bash
sudo nano /opt/bas-executor/.env
```

Example:

```dotenv
EXECUTOR_SECRET=<nilai-BAS_EXECUTOR_SECRET-dari-AI-VM>
EXECUTOR_BIND_HOST=<BAS_PRIVATE_IP>
EXECUTOR_PORT=8010

ENGAGEMENT_FILE=/opt/bas-executor/engagements/active.yaml
CREDENTIAL_FILE=/opt/bas-executor/secrets/credentials.yaml
ARTIFACT_DIR=/var/lib/bas-executor/artifacts

CALDERA_URL=http://127.0.0.1:8888
CALDERA_API_KEY=<caldera-key-baru>

BLOODHOUND_URL=http://127.0.0.1:8080
BLOODHOUND_TOKEN_ID=<bloodhound-api-token-id>
BLOODHOUND_TOKEN_KEY=<bloodhound-api-token-key>

BUBBLEWRAP_PATH=/usr/bin/bwrap
SHELL_PATH=/bin/bash
SHELL_READONLY_BINDS=/usr,/bin,/lib,/lib64,/etc/resolv.conf,/etc/hosts,/etc/nsswitch.conf,/etc/ssl/certs,/etc/passwd,/etc/group
```

Create a BloodHound API token with read-only graph permission. The adapter uses
`bhesignature`, not a username/password.

If a tool is installed outside `/usr`, add its exact root to
`SHELL_READONLY_BINDS`. Example:

```dotenv
SHELL_READONLY_BINDS=/usr,/bin,/lib,/lib64,/opt/netexec
```

Never bind:

```text
/opt
/opt/bas-executor
/opt/bas-executor/secrets
/
```

Binding those paths would expose secrets to generic shell.

## 12. Configure active engagement

```bash
sudo nano /opt/bas-executor/engagements/active.yaml
```

Example:

```yaml
engagement_id: private-lab-001
active: true
owner: lab-owner
scope:
  cidrs:
    - 10.100.31.0/24
  domains:
    - cs.lab
  caldera_groups:
    - red
  caldera_adversaries:
    - <approved-adversary-id>
policy:
  automatic_categories:
    - read_only
    - active_scan
  approval_categories:
    - authenticated_enumeration
    - adversary_emulation
    - remote_execution
    - credential_access
    - c2_tasking
    - phishing
  denied_categories:
    - destructive
    - denial_of_service
    - log_deletion
```

Categories not listed in any policy list are denied.

## 13. Test bubblewrap

Run as the service user:

```bash
sudo -u bas-agent /usr/bin/bwrap \
  --ro-bind /usr /usr \
  --ro-bind-try /bin /bin \
  --ro-bind-try /lib /lib \
  --ro-bind-try /lib64 /lib64 \
  --proc /proc \
  --dev /dev \
  --tmpfs /tmp \
  -- /bin/bash --noprofile --norc -c 'id && test ! -e /opt/bas-executor/.env'
```

The command should display the `bas-agent` identity and return success because
the `.env` path is not mounted.

If bubblewrap is blocked by host policy, fix the host policy. Do not modify the
executor to fall back to an unsandboxed shell.

## 14. Start BAS Executor

```bash
sudo cp /opt/bas-executor/systemd/bas-executor.service \
  /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now bas-executor
sudo systemctl status bas-executor
sudo journalctl -u bas-executor -n 100 --no-pager
```

Health locally:

```bash
curl http://127.0.0.1:8010/health
```

If binding to the private IP:

```bash
curl "http://<BAS_PRIVATE_IP>:8010/health"
```

## 15. BAS firewall

Allow API access only from AI VM:

```bash
sudo ufw allow from <AI_VM_IP> to <BAS_PRIVATE_IP> port 8010 proto tcp
sudo ufw deny 8010/tcp
sudo ufw enable
sudo ufw status numbered
```

For shell and scanning safety, configure an egress boundary that permits only
the engagement CIDRs and required DNS/NTP infrastructure. The exact rule depends
on your lab routing. Static command validation cannot replace network egress
enforcement.

## 16. Direct BAS smoke tests

On BAS VM:

```bash
cd /opt/bas-executor
set -a
source .env
set +a
```

CALDERA list:

```bash
python scripts/signed_request.py \
  --capability caldera.list_operations \
  --case-id smoke-caldera
```

Daftar seluruh capability BAS yang terpasang:

```bash
python scripts/signed_request.py \
  --capability bas.list_capabilities \
  --case-id smoke-capabilities
```

Typed capability tetap direkomendasikan. Semua binary lain yang terlihat di
dalam bubblewrap dapat digunakan lewat `shell.execute`, tetapi selalu memerlukan
approval, target yang dideklarasikan, engagement scope, dan egress firewall.

BloodHound read-only query:

```bash
python scripts/signed_request.py \
  --capability bloodhound.cypher_query \
  --case-id smoke-bloodhound \
  --arguments '{"query":"MATCH (n:Computer) RETURN n LIMIT 5","include_properties":true}'
```

Shell without approval must return `pending_approval`:

```bash
python scripts/signed_request.py \
  --capability shell.execute \
  --case-id smoke-shell \
  --arguments '{"command":"nmap -sn 10.100.31.0/30","targets":["10.100.31.0/30"],"timeout":120}'
```

Admin-only approval test:

```bash
python scripts/signed_request.py \
  --capability shell.execute \
  --case-id smoke-shell-approved \
  --approved \
  --arguments '{"command":"nmap -sn 10.100.31.0/30","targets":["10.100.31.0/30"],"timeout":120}'
```

Artifacts:

```bash
sudo find /var/lib/bas-executor/artifacts -maxdepth 3 -type f -ls
```

## 17. Test Security Agent

On AI VM:

```bash
cd ~/security-ai-lab/security-agent
set -a
source .env
set +a
```

No tools:

```bash
curl -X POST http://127.0.0.1:8000/v1/investigate \
  -H "Content-Type: application/json" \
  -H "X-API-Key: ${API_KEY}" \
  -d '{
    "profile": "soc",
    "objective": "Jelaskan scope lab. Jangan jalankan tool.",
    "allow_tools": false
  }'
```

Active scan request does not need `X-Approval-Key`, but BAS still validates the
target locally:

```bash
curl -X POST http://127.0.0.1:8000/v1/investigate \
  -H "Content-Type: application/json" \
  -H "X-API-Key: ${API_KEY}" \
  -d '{
    "profile": "redteam",
    "objective": "Gunakan bas_execute capability nxc.smb_discover pada 10.100.31.20.",
    "evidence": ["Target berada dalam engagement aktif"]
  }'
```

Approved shell:

```bash
curl -X POST http://127.0.0.1:8000/v1/investigate \
  -H "Content-Type: application/json" \
  -H "X-API-Key: ${API_KEY}" \
  -H "X-Approval-Key: ${APPROVAL_KEY}" \
  -d '{
    "profile": "redteam",
    "objective": "Gunakan bas_execute shell.execute untuk menjalankan nmap -sn 10.100.31.0/30. Deklarasikan targets.",
    "approved_capabilities": ["shell.execute"],
    "evidence": ["Approval diberikan untuk discovery pada CIDR engagement"]
  }'
```

Without the approval header, any non-empty `approved_capabilities` request is
rejected with HTTP 403.

## 18. CALDERA workflow

1. `caldera.list_agents`
2. `caldera.list_adversaries`
3. Add approved adversary and group to engagement.
4. Generate a plan without launch.
5. Approve exactly `caldera.launch_operation`.
6. Poll `caldera.get_operation`.
7. Retrieve `caldera.get_operation_report`.
8. Retrieve `caldera.get_operation_event_logs` when timeline detail is needed.
9. Correlate UTC timestamps with ExtraHop and CrowdStrike.

CALDERA launch requires:

```json
{
  "name": "operation-name",
  "adversary": "allowlisted-adversary-id",
  "group": "allowlisted-group",
  "planner": "atomic",
  "source": "basic"
}
```

## 19. BloodHound workflow

Use only read-only Cypher:

```cypher
MATCH (c:Computer)
RETURN c
LIMIT 25
```

The adapter rejects semicolon-separated statements and mutation keywords such
as `CREATE`, `MERGE`, `DELETE`, `SET`, `REMOVE`, `DROP`, `LOAD CSV`, `FOREACH`,
and `CALL`.

Use BloodHound credentials with only GraphDB read permission. Server-side
permission enforcement remains required even though the adapter also validates
the query.

## 20. Purple-team validation

1. Define one ATT&CK hypothesis.
2. Query ExtraHop and CrowdStrike baseline through MCP.
3. Run one approved BAS/CALDERA capability.
4. Record case ID, operation ID, UTC timestamps, source, target, and user.
5. Retrieve CALDERA report/event logs.
6. Query ExtraHop and CrowdStrike using the same entities and time window.
7. Classify `detected`, `telemetry-only`, `not-detected`, or `not-observable`.
8. Complete `security-agent/docs/report-template.md`.

## 21. RAG update

Place sanitized Markdown under:

```text
security-agent/knowledge/
```

Then run reindex. Suitable content:

- Topology and asset roles.
- Approved runbooks.
- Detection mapping.
- False-positive notes.
- Remediation standards.
- Sanitized lessons learned.

Do not add secret, reusable credential/hash, active engagement, raw evidence, or
untrusted prompt instructions.

## 22. Operasional harian

AI VM:

```bash
docker compose ps
docker compose logs --tail=200 agent
docker compose logs --tail=200 llama
docker stats
free -h
df -h
```

BAS VM:

```bash
sudo systemctl status bas-executor
sudo journalctl -u bas-executor -n 200 --no-pager
sudo find /var/lib/bas-executor/artifacts -maxdepth 3 -type f -ls
```

## 23. Troubleshooting

### llama.cpp mati karena RAM

Pastikan context `4096`, batch `128`, parallel `1`, dan hanya satu model yang
berjalan. Periksa `docker stats` dan `dmesg -T | grep -i -E 'oom|killed'`.

### Request investigate timeout

Pada CPU-only 4 vCPU, gunakan `LLM_DISABLE_THINKING=true`,
`LLM_PLAN_MAX_TOKENS=350`, dan `LLM_REPORT_MAX_TOKENS=650`. Request tanpa tool
melewati planning LLM. Gunakan timeout client minimal 300 detik untuk workflow
yang memakai tool dan menghasilkan report kedua.

### Agent gagal start

`API_KEY`, `APPROVAL_KEY`, dan `BAS_EXECUTOR_SECRET` harus berbeda, bukan
placeholder, dan minimal 32 karakter.

### BAS gagal start

Periksa `EXECUTOR_SECRET`, file engagement, permission directory, dan bind IP:

```bash
sudo journalctl -u bas-executor -n 100 --no-pager
ip address
```

### Shell gagal

Periksa:

```bash
command -v bwrap
sudo -u bas-agent bwrap --version
```

Jangan menambahkan fallback unsandboxed.

### Target ditolak

Perbaiki engagement jika target memang authorized. Jangan menonaktifkan
validation.

### BloodHound 401/403

Periksa clock, token ID/key, GraphDB read permission, dan URL. Request signature
bersifat time-sensitive.

### CALDERA report gagal

Pastikan CALDERA mendukung API v2 dan operation ID valid. Endpoint yang
digunakan adalah:

```text
POST /api/v2/operations/{id}/report
POST /api/v2/operations/{id}/event-logs
```

## 24. Test repository

```bash
python3 -m venv .venv-test
. .venv-test/bin/activate
pip install -e './security-agent[dev]' -e './bas-executor[dev]'

cd security-agent && pytest -q
cd ../bas-executor && pytest -q
```

Panduan test lebih lengkap: [TESTING.md](TESTING.md).

## 25. Git workflow

Before commit:

```bash
./scripts/check-no-secrets.sh
git status --short
```

Yang tidak boleh masuk Git:

- `.env`
- Model GGUF
- `engagements/active.yaml`
- `secrets/credentials.yaml`
- Active evidence/artifact directories
- Customer telemetry

Push:

```bash
git add .
git commit -m "Harden policy and add BAS integrations"
git push
```
