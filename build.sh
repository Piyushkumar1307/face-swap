#!/usr/bin/env bash
# Render build: API + FaceFusion + frontend static bundle.
set -euo pipefail
cd "$(dirname "$0")"
pip install -r requirements.txt
python -c "import cv2; print('opencv', cv2.__version__)"
bash scripts/build_frontend.sh
cd backend
bash scripts/render-build.sh
