#!/usr/bin/env bash
# Production API (no --reload). Bind localhost; nginx handles public traffic.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
exec bash "$ROOT/start.sh"
