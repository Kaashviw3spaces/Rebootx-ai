#!/usr/bin/env bash
# ==============================================================================
# REBOOTX — Linux / macOS Setup Wrapper
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

cd "${PROJECT_ROOT}"

# Check for Python 3
if command -v python3 >/dev/null 2>&1; then
    PYTHON_CMD="python3"
elif command -v python >/dev/null 2>&1; then
    PYTHON_CMD="python"
else
    echo "[ERROR] Python 3.10+ is required but not found in PATH." >&2
    exit 1
fi

exec "${PYTHON_CMD}" scripts/setup.py "$@"

