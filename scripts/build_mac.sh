#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${ROOT_DIR}"

PYTHON_BIN="${PYTHON_BIN:-python3}"

"${PYTHON_BIN}" -m PyInstaller \
  --noconfirm \
  --clean \
  SuperEXIF_mac.spec

echo "[OK] 打包完成: dist/SuperEXIF.app"
