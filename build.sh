#!/usr/bin/env bash
# Render build: install API deps, clone FaceFusion, download models.
set -euo pipefail
cd "$(dirname "$0")"
pip install -r requirements.txt
cd backend
bash scripts/render-build.sh
