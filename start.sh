#!/usr/bin/env bash
# Start API immediately; missing models download in background (see main.py startup).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/backend" && pwd)"
cd "$ROOT"

export PATH="$ROOT/bin:$PATH"
export FACEFUSION_PYTHON="${FACEFUSION_PYTHON:-python}"

echo "[start] Starting API (models download in background if needed)..."
exec "$FACEFUSION_PYTHON" -m uvicorn main:app --host 0.0.0.0 --port "${PORT:-8000}"
