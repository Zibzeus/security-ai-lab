#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
AGENT_DIR="${ROOT}/security-agent"
cd "${AGENT_DIR}"

if [[ ! -f .env ]]; then
  echo "Missing security-agent/.env; refusing to deploy." >&2
  exit 1
fi
if [[ ! -f models/Qwen3-4B-Q4_K_M.gguf ]]; then
  echo "Missing Qwen3 GGUF model; refusing to deploy." >&2
  exit 1
fi
if [[ ! -f local-certs/extrahop-mcp.crt ]]; then
  echo "Missing ExtraHop MCP CA certificate; refusing to deploy." >&2
  exit 1
fi

for variable in WEB_USERNAME WEB_PASSWORD_HASH WEB_SESSION_SECRET; do
  if ! grep -q "^${variable}=." .env; then
    echo "Missing ${variable} in security-agent/.env." >&2
    exit 1
  fi
done

mkdir -p rag-sources
chmod 755 rag-sources
find rag-sources -type d -exec chmod 755 {} +
find rag-sources -type f -exec chmod 644 {} +

if grep -q '^KNOWLEDGE_DIRS=' .env; then
  if ! grep '^KNOWLEDGE_DIRS=' .env | grep -q '/app/rag-sources'; then
    sed -i \
      's|^KNOWLEDGE_DIRS=.*|KNOWLEDGE_DIRS=/app/knowledge,/app/docs,/app/rag-sources|' \
      .env
  fi
else
  printf '%s\n' \
    'KNOWLEDGE_DIRS=/app/knowledge,/app/docs,/app/rag-sources' >> .env
fi

chmod 600 .env
backup_name="security-agent-$(date -u +%Y%m%dT%H%M%SZ).db"
if docker compose ps --status running agent --quiet | grep -q .; then
  docker compose exec -T agent python - "${backup_name}" <<'PY'
import sqlite3
import sys

source = sqlite3.connect("/data/security-agent.db")
target = sqlite3.connect(f"/data/{sys.argv[1]}")
source.backup(target)
target.close()
source.close()
print(f"SQLite backup created: /data/{sys.argv[1]}")
PY
fi

docker compose config >/dev/null
docker compose build agent
docker compose up -d --force-recreate agent
docker compose up -d caddy

for _ in $(seq 1 60); do
  if curl -fsS http://127.0.0.1:8000/health >/dev/null; then
    break
  fi
  sleep 2
done
curl -fsS http://127.0.0.1:8000/health

api_key="$(sed -n 's/^API_KEY=//p' .env | tail -n 1)"
if [[ -z "${api_key}" ]]; then
  echo "API_KEY is missing; deployment succeeded but RAG was not reindexed." >&2
  exit 1
fi

curl -fsS -X POST http://127.0.0.1:8000/v1/knowledge/reindex \
  -H "X-API-Key: ${api_key}"
unset api_key

docker compose ps
echo
echo "Deployment complete. Validate HTTPS at https://10.100.31.3/"
