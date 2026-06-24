#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MODEL_DIR="${ROOT}/security-agent/models"
MODEL_FILE="Qwen3-4B-Q4_K_M.gguf"

command -v python3 >/dev/null || {
  echo "python3 is required" >&2
  exit 1
}

python3 -m venv "${ROOT}/.model-download-venv"
"${ROOT}/.model-download-venv/bin/pip" install --upgrade pip huggingface_hub
mkdir -p "${MODEL_DIR}"
"${ROOT}/.model-download-venv/bin/hf" download \
  Qwen/Qwen3-4B-GGUF \
  "${MODEL_FILE}" \
  --local-dir "${MODEL_DIR}"

sha256sum "${MODEL_DIR}/${MODEL_FILE}" | tee "${MODEL_DIR}/${MODEL_FILE}.sha256"
echo "Model ready: ${MODEL_DIR}/${MODEL_FILE}"
