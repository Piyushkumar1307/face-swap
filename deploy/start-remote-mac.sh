#!/usr/bin/env bash
# Mac: run API + Cloudflare quick tunnel (public https URL, changes each run).
# Install cloudflared once: brew install cloudflared
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

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
  echo "cloudflared not found. Install one of:"
  echo "  brew install cloudflared"
  echo "  https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/"
  exit 1
fi

if [[ ! -f "$ROOT/backend/static/index.html" ]]; then
  echo "Frontend not built yet — building into backend/static..."
  bash "$ROOT/scripts/build_frontend.sh"
fi

echo "Starting API in background on port 8000..."
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
echo "Local UI (test here first):  http://127.0.0.1:8000"
echo "Starting tunnel — public URL will appear below in a few seconds..."
echo "Keep this Mac awake and this terminal open."
echo ""

print_public_url() {
  local url="$1"
  echo ""
  echo "================================================================"
  echo "  PUBLIC URL — copy and share (changes each run):"
  echo ""
  echo "  ${url}"
  echo ""
  echo "================================================================"
  echo ""
  if command -v pbcopy >/dev/null 2>&1; then
    printf '%s' "$url" | pbcopy
    echo "  (URL copied to clipboard — paste in chat or scan as QR)"
    echo ""
  fi
}

public_url_printed=0
while IFS= read -r line; do
  echo "$line"
  if [[ $public_url_printed -eq 0 ]] && [[ "$line" =~ (https://[a-zA-Z0-9-]+\.trycloudflare\.com) ]]; then
    public_url_printed=1
    print_public_url "${BASH_REMATCH[1]}"
  fi
done < <("$CF" tunnel --url http://127.0.0.1:8000 2>&1)
