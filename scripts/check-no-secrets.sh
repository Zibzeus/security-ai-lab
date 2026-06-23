#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}"

if git ls-files | grep -E '(^|/)(\.env|active\.yaml|credentials\.yaml)$|\.gguf$'; then
  echo "Sensitive or large runtime files are tracked by Git." >&2
  exit 1
fi

MATCHES="$(
  git grep -nEi \
    '(password|api[_-]?key|client[_-]?secret|bearer[_-]?token)[[:space:]]*[:=][[:space:]]*[^<${[:space:]]{8,}' \
    -- ':!*.example' ':!docs/*' || true
)"
FILTERED="$(
  printf '%s\n' "${MATCHES}" |
    grep -Eiv 'YOUR_KEY|replace-me|change-me|example|placeholder' || true
)"

if [[ -n "${FILTERED}" ]]; then
  printf '%s\n' "${FILTERED}"
  echo "Possible hard-coded secret found. Review before pushing." >&2
  exit 1
fi

echo "No obvious tracked runtime secrets found."
