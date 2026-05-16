#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/backend" && pwd)"
cd "$ROOT"

export PATH="$ROOT/bin:$PATH"
export FACEFUSION_PYTHON="${FACEFUSION_PYTHON:-python}"

echo "[start] Checking FaceFusion..."
if ! "$FACEFUSION_PYTHON" -c "from facefusion_runner import is_facefusion_ready; import sys; sys.exit(0 if is_facefusion_ready() else 1)"; then
  echo "[start] Models missing — running selective download (may take several minutes)..."
  "$FACEFUSION_PYTHON" scripts/download_swap_models.py
fi

if ! "$FACEFUSION_PYTHON" -c "from facefusion_runner import is_facefusion_ready; import sys; sys.exit(0 if is_facefusion_ready() else 1)"; then
  echo "[start] ERROR: FaceFusion is not ready after model download." >&2
  exit 1
fi

echo "[start] FaceFusion ready. Starting API..."
exec "$FACEFUSION_PYTHON" -m uvicorn main:app --host 0.0.0.0 --port "${PORT:-8000}"
