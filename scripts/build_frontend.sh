#!/usr/bin/env bash
# Build Vite frontend into backend/static for single-service deploy.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
FRONTEND="$ROOT/frontend"
STATIC="$ROOT/backend/static"

if ! command -v npm >/dev/null 2>&1; then
  echo "ERROR: npm is required to build the frontend." >&2
  exit 1
fi

cd "$FRONTEND"
export VITE_API_URL="${VITE_API_URL:-}"

echo "[build] Building frontend (VITE_API_URL=${VITE_API_URL:-<same origin>})..."
if [[ -f package-lock.json ]]; then
  npm ci
else
  npm install
fi
npm run build

rm -rf "$STATIC"
mkdir -p "$STATIC"
cp -r dist/. "$STATIC/"
echo "[build] Frontend ready at backend/static/"
