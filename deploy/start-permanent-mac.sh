#!/usr/bin/env bash
# Mac: API + permanent Cloudflare tunnel (same URL every time).
# One-time setup: bash deploy/setup-permanent-tunnel-mac.sh
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
CONFIG="$ROOT/deploy/cloudflared/config.yml"

CF=""
for candidate in cloudflared /opt/homebrew/bin/cloudflared /usr/local/bin/cloudflared; do
  if command -v "$candidate" >/dev/null 2>&1; then
    CF="$candidate"
    break
  fi
  if [[ -x "$candidate" ]]; then
    CF="$candidate"
    break
  fi
done
if [[ -z "$CF" ]]; then
  echo "cloudflared not found. Install: brew install cloudflared"
  exit 1
fi

if [[ ! -f "$CONFIG" ]]; then
  echo "No permanent tunnel config yet."
  echo "Run once: bash deploy/setup-permanent-tunnel-mac.sh"
  exit 1
fi

HOSTNAME="$(grep -E '^\s+hostname:' "$CONFIG" | head -1 | sed -E 's/.*hostname:\s*//')"

if [[ ! -f "$ROOT/backend/static/index.html" ]]; then
  echo "Building frontend into backend/static..."
  bash "$ROOT/scripts/build_frontend.sh"
fi

echo "Starting API on port 8000..."
bash "$ROOT/start.sh" &
API_PID=$!
trap 'kill $API_PID 2>/dev/null || true' EXIT

echo "Waiting for API..."
for _ in $(seq 1 30); do
  if curl -sf http://127.0.0.1:8000/api/health >/dev/null 2>&1; then
    break
  fi
  sleep 1
done

echo ""
if [[ -n "$HOSTNAME" ]]; then
  echo "Fixed public URL (bookmark this):  https://${HOSTNAME}"
else
  echo "Public URL: see hostname in deploy/cloudflared/config.yml"
fi
echo "Local test:  http://127.0.0.1:8000"
echo "Keep this Mac awake and this terminal open."
echo ""

"$CF" tunnel --config "$CONFIG" run face-swap
