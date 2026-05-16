#!/usr/bin/env bash
# Start API immediately; missing models download in background (see main.py startup).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/backend" && pwd)"
cd "$ROOT"

export PATH="$ROOT/bin:$PATH"

resolve_python() {
  local py="${1:-python}"
  if [[ "$py" = /* ]] && [[ -x "$py" ]]; then
    echo "$py"
    return
  fi
  if [[ -x "$ROOT/$py" ]]; then
    echo "$ROOT/$py"
    return
  fi
  if command -v "$py" >/dev/null 2>&1; then
    command -v "$py"
    return
  fi
  if command -v python3 >/dev/null 2>&1; then
    command -v python3
    return
  fi
  command -v python
}

REQUESTED="${FACEFUSION_PYTHON:-python}"
PYTHON_BIN="$(resolve_python "$REQUESTED")"
if [[ "$REQUESTED" != "$PYTHON_BIN" ]] && [[ "$REQUESTED" != "python" ]]; then
  echo "[start] FACEFUSION_PYTHON=$REQUESTED not found — using $PYTHON_BIN"
fi
export FACEFUSION_PYTHON="$PYTHON_BIN"

echo "[start] Python: $PYTHON_BIN"
echo "[start] Starting API (models download in background if needed)..."
exec "$PYTHON_BIN" -m uvicorn main:app --host 0.0.0.0 --port "${PORT:-8000}"
