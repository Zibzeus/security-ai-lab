#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FAILED=0

check() {
  if "$@" >/dev/null 2>&1; then
    printf "[OK] %s\n" "$*"
  else
    printf "[FAIL] %s\n" "$*"
    FAILED=1
  fi
}

check command -v docker
check docker compose version
check test -f "${ROOT}/security-agent/.env"
check test -f "${ROOT}/security-agent/models/Qwen3-4B-Q4_K_M.gguf"
check test -f "${ROOT}/security-agent/policies/default.yaml"
check test -f "${ROOT}/security-agent/connectors/mcp.yaml"
check test -f "${ROOT}/security-agent/models/Qwen3-4B-Q4_K_M.gguf.sha256"
check docker compose -f "${ROOT}/security-agent/docker-compose.yml" config
check sha256sum -c "${ROOT}/security-agent/models/Qwen3-4B-Q4_K_M.gguf.sha256"

read_env() {
  local name="$1"
  sed -n "s/^${name}=//p" "${ROOT}/security-agent/.env" | tail -n 1
}

check_secret() {
  local name="$1"
  local value
  value="$(read_env "${name}")"
  if [[ "${#value}" -lt 32 || "${value}" == replace-* || "${value}" == change-me* ]]; then
    printf "[FAIL] %s must be a non-placeholder value of 32+ characters\n" "${name}"
    FAILED=1
  else
    printf "[OK] %s is configured\n" "${name}"
  fi
}

if [[ -f "${ROOT}/security-agent/.env" ]]; then
  check_secret API_KEY
  check_secret APPROVAL_KEY
  check_secret BAS_EXECUTOR_SECRET
fi

if [[ "${FAILED}" -ne 0 ]]; then
  echo "Preflight failed. Resolve the failed checks before deployment." >&2
  exit 1
fi

echo "Security Agent VM preflight passed."
