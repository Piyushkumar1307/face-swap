#!/usr/bin/env bash
# Render build: API + FaceFusion + frontend static bundle.
set -euo pipefail
cd "$(dirname "$0")"
pip install -r requirements.txt
bash scripts/build_frontend.sh
cd backend
bash scripts/render-build.sh
