#!/usr/bin/env bash
# Render.com build: API deps + FaceFusion + bundled ffmpeg (no Homebrew).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

pip install -r requirements.txt

if [[ ! -d facefusion ]]; then
  echo "Cloning FaceFusion..."
  git clone --depth 1 https://github.com/facefusion/facefusion.git facefusion
fi

pip install -r facefusion/requirements.txt "onnxruntime==1.24.4" imageio-ffmpeg

mkdir -p bin
FF_EXE="$(python -c "import imageio_ffmpeg; print(imageio_ffmpeg.get_ffmpeg_exe())")"
ln -sf "$FF_EXE" bin/ffmpeg
echo "ffmpeg: $FF_EXE"

cd facefusion
export PATH="$ROOT/bin:$PATH"
echo "Downloading FaceFusion models (may take several minutes)..."
python facefusion.py force-download --log-level info || echo "WARN: model download incomplete; first swap may retry downloads."
