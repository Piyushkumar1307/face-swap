#!/usr/bin/env bash
# Render.com build: API deps + FaceFusion + swap-only models (avoids 10GB+ force-download).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DEBUG_LOG="$ROOT/../.cursor/debug-d365c7.log"
cd "$ROOT"

#region agent log
_log() {
  local hid="$1" msg="$2"
  python3 -c "
import json,time,os
p=os.environ.get('DEBUG_LOG','')
if p:
  os.makedirs(os.path.dirname(p),exist_ok=True)
  open(p,'a').write(json.dumps({'sessionId':'d365c7','hypothesisId':'$hid','location':'render-build.sh','message':'$msg','data':{},'timestamp':int(time.time()*1000)})+'\n')
" 2>/dev/null || true
}
#endregion

_log "H1" "render-build started"
export DEBUG_LOG

pip install -r requirements.txt

install_facefusion() {
  echo "Cloning FaceFusion..."
  rm -rf facefusion
  git clone --depth 1 https://github.com/facefusion/facefusion.git facefusion
}

if [[ ! -f facefusion/facefusion.py ]] || [[ ! -f facefusion/requirements.txt ]]; then
  install_facefusion
fi

if [[ ! -f facefusion/requirements.txt ]]; then
  echo "ERROR: FaceFusion clone failed — requirements.txt missing"
  _log "H2" "facefusion clone failed"
  exit 1
fi

_log "H2" "facefusion present"

pip install -r facefusion/requirements.txt "onnxruntime==1.24.4" imageio-ffmpeg
# Headless OpenCV for Linux servers (provides cv2; avoids missing GUI libs on Render).
pip install "opencv-python-headless==4.10.0.84"
python -c "import cv2; print('opencv', cv2.__version__)"

mkdir -p bin
FF_EXE="$(python -c "import imageio_ffmpeg; print(imageio_ffmpeg.get_ffmpeg_exe())")"
ln -sf "$FF_EXE" bin/ffmpeg
echo "ffmpeg: $FF_EXE"

export PATH="$ROOT/bin:$PATH"

if [[ "${FACEFUSION_SKIP_BUILD_DOWNLOAD:-}" == "1" ]]; then
  echo "Skipping model download (FACEFUSION_SKIP_BUILD_DOWNLOAD=1)"
  _log "H5" "skipped model download by env"
  exit 0
fi

_log "H1" "starting selective model download"
echo "Downloading swap-only FaceFusion models (~2-4GB, not full force-download)..."
python scripts/download_swap_models.py

SWAP_ONNX="facefusion/.assets/models/${FACEFUSION_SWAP_MODEL:-inswapper_128_fp16}.onnx"
if [[ ! -f "$SWAP_ONNX" ]]; then
  echo "ERROR: swap model missing after download: $SWAP_ONNX" >&2
  _log "H7" "swap model file missing" 
  exit 1
fi

echo "[build] Model files verified on disk."

if [[ ! -f static/index.html ]]; then
  echo "ERROR: frontend missing — build.sh must run scripts/build_frontend.sh first." >&2
  exit 1
fi
echo "[build] Frontend static bundle present."

_log "H1" "render-build finished"
