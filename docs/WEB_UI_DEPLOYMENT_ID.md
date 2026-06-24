# Deployment Web UI Security AI Lab

Panduan ini menambahkan console Web langsung di:

```text
https://10.100.31.3/
```

Komponen baru tetap ringan:

- FastAPI menyajikan API dan static Web UI.
- SQLite menyimpan case, percakapan, evidence, hasil tool, approval, dan audit.
- Caddy menjadi satu-satunya service yang dibuka ke LAN pada port 80/443.
- Agent tetap hanya dipublikasikan pada `127.0.0.1:8000`.
- Caddy menggunakan internal CA untuk sertifikat IP `10.100.31.3`.

Full conversation history disimpan di SQLite. Hanya delapan turn terakhir,
masing-masing maksimum 1.200 karakter, yang dikirim ke model secara default.

## 1. Prasyarat

```bash
cd ~/security-ai-lab/security-agent
docker compose ps
curl http://127.0.0.1:8000/health
sudo ss -lntup | grep -E ':(80|443)\b' || true
```

Port 80 dan 443 harus kosong. Jika dipakai service lain, identifikasi service
tersebut sebelum melanjutkan.

## 2. Backup sebelum upgrade

```bash
cd ~/security-ai-lab/security-agent
umask 077
cp .env "$HOME/security-agent.env.before-web"

docker compose exec agent python -c '
import sqlite3
source = sqlite3.connect("/data/security-agent.db")
target = sqlite3.connect("/data/security-agent.before-web.db")
source.backup(target)
target.close()
source.close()
print("SQLite backup complete")
'
```

Backup `.env` berisi secret. Jangan upload ke Git, chat, atau shared storage.

## 3. Pasang source baru

Jika perubahan sudah berada di GitHub:

```bash
cd ~/security-ai-lab
git pull --ff-only origin main
```

Jika menggunakan archive dari Codex, transfer archive ke AI VM dan
pertahankan file runtime berikut:

```text
security-agent/.env
security-agent/models/
security-agent/local-certs/
```

## 4. Konfigurasi login

```bash
cd ~/security-ai-lab/security-agent
docker compose build agent
```

Generate password hash secara interaktif:

```bash
docker compose run --rm --no-deps \
  --entrypoint python agent \
  /app/scripts/hash_web_password.py
```

Password minimum 12 karakter. Copy output yang dimulai dengan `scrypt$`.

Generate session secret:

```bash
openssl rand -hex 32
```

Edit `.env`:

```bash
nano .env
```

Tambahkan:

```dotenv
WEB_USERNAME=admin
WEB_PASSWORD_HASH=scrypt$...
WEB_SESSION_SECRET=PASTE_RANDOM_64_HEX
WEB_SESSION_TTL_SECONDS=28800
WEB_MEMORY_TURNS=8
WEB_MEMORY_CHARS_PER_TURN=1200
WEB_SECURE_COOKIE=true
ENABLE_API_DOCS=false
```

Jika update `.env` dari shell, jangan pakai `echo "WEB_PASSWORD_HASH=scrypt$..."`
karena `$...` dapat diproses sebagai variable shell. Pakai editor, atau pakai
single-quoted heredoc:

```bash
python3 - <<'PY'
from pathlib import Path

env = Path(".env")
lines = env.read_text(encoding="utf-8").splitlines()
updates = {
    "WEB_USERNAME": "admin",
    "WEB_PASSWORD_HASH": "PASTE_SCRYPT_HASH_HERE",
}
seen = set()
out = []
for line in lines:
    key = line.split("=", 1)[0] if "=" in line else ""
    if key in updates:
        out.append(f"{key}={updates[key]}")
        seen.add(key)
    else:
        out.append(line)
for key, value in updates.items():
    if key not in seen:
        out.append(f"{key}={value}")
env.write_text("\n".join(out) + "\n", encoding="utf-8")
PY
```

Jangan menggunakan `APPROVAL_KEY`, `API_KEY`, atau `BAS_EXECUTOR_SECRET` sebagai
password atau session secret.

Periksa tanpa menampilkan secret:

```bash
awk -F= '
/^WEB_USERNAME=/{print "web_username=" $2}
/^WEB_PASSWORD_HASH=/{print "password_hash_configured=" (length($2)>20)}
/^WEB_SESSION_SECRET=/{print "session_secret_length=" length($2)}
' .env
```

Verifikasi password tanpa menampilkan password/hash:

```bash
docker compose run --rm --no-deps \
  --entrypoint python agent \
  /app/scripts/verify_web_password.py
```

Output yang benar:

```text
password_hash_configured=True
password_ok=True
```

## 5. Periksa MCP dan CA

`connectors/mcp.yaml`:

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

```bash
test -f local-certs/extrahop-mcp.crt
```

## 6. Deploy

```bash
docker compose config >/dev/null
docker compose build agent
docker compose up -d --force-recreate agent
docker compose up -d caddy
docker compose ps
```

Periksa:

```bash
docker compose logs --tail=100 agent
docker compose logs --tail=100 caddy
curl http://127.0.0.1:8000/health
curl -kI https://10.100.31.3/
```

`curl -k` hanya digunakan sebelum CA dipercaya oleh workstation.

## 7. Firewall AI VM

Contoh berikut membuka UI hanya untuk subnet lab:

```bash
sudo ufw allow from 10.100.31.0/24 to any port 443 proto tcp
sudo ufw allow from 10.100.31.0/24 to any port 80 proto tcp
sudo ufw deny 443/tcp
sudo ufw deny 80/tcp
sudo ufw status numbered
```

Jangan membuka port 8000 ke LAN.

## 8. Trust Caddy internal CA pada Windows

Export public root certificate:

```bash
docker compose cp \
  caddy:/data/caddy/pki/authorities/local/root.crt \
  ./local-certs/security-ai-web-root.crt
```

Copy ke workstation:

```powershell
scp autoadmin@10.100.31.3:/home/autoadmin/security-ai-lab/security-agent/local-certs/security-ai-web-root.crt .
```

Tampilkan fingerprint pada AI VM:

```bash
openssl x509 \
  -in local-certs/security-ai-web-root.crt \
  -noout -subject -fingerprint -sha256
```

Bandingkan pada Windows:

```powershell
certutil -hashfile .\security-ai-web-root.crt SHA256
```

Setelah fingerprint cocok:

```powershell
certutil -user -addstore Root .\security-ai-web-root.crt
```

Restart browser dan buka:

```text
https://10.100.31.3/
```

Private key internal CA tetap berada di volume `caddy-data`. Jangan menyalin
private key tersebut.

## 9. Smoke test Web UI

1. Login.
2. Buat case SOC.
3. Kirim pesan tanpa tools.
4. Refresh browser dan pastikan history tetap ada.
5. Periksa status LLM, BAS, ExtraHop, dan CrowdStrike.
6. Jalankan satu query read-only.
7. Periksa Audit log.
8. Minta capability BAS yang membutuhkan approval.
9. Review capability dan exact arguments.
10. Uji `Reject` terlebih dahulu.
11. Setelah scope benar, klik `Approve and execute` dan masukkan
    `APPROVAL_KEY` yang terpisah dari password login.

Approval key hanya dikirim untuk action tersebut dan tidak disimpan di
SQLite, cookie, atau browser storage.

## 10. Memory dan resource

```dotenv
WEB_MEMORY_TURNS=8
WEB_MEMORY_CHARS_PER_TURN=1200
AGENT_MEMORY_LIMIT=768m
LLAMA_MEMORY_LIMIT=5500m
LLM_CONTEXT_SIZE=2048
```

- Seluruh history case tetap tersimpan di SQLite.
- `WEB_MEMORY_TURNS` mengatur turn terakhir yang dikirim ke LLM.
- Menaikkan context model meningkatkan RAM dan latency.
- Pada VM 8 GB, pertahankan context 2.048 sampai monitoring menunjukkan
  headroom yang cukup.

```bash
docker stats $(docker compose ps -q) --no-stream
free -h
```

## 11. Backup dan rollback

Backup berkala:

```bash
docker compose exec agent python -c '
import sqlite3
source = sqlite3.connect("/data/security-agent.db")
target = sqlite3.connect("/data/security-agent.manual-backup.db")
source.backup(target)
target.close()
source.close()
print("SQLite backup complete")
'
```

Untuk menghentikan Web UI tanpa menghapus data:

```bash
docker compose stop caddy
```

Jangan menjalankan `docker compose down -v`; opsi `-v` akan menghapus volume
SQLite dan internal CA.
