#!/usr/bin/env bash
# One-time setup on your own PC (Linux/macOS). Run from repo root.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BACKEND="$ROOT/backend"
FF="$BACKEND/facefusion"
VENV_FF="$BACKEND/venv-ff"

cd "$ROOT"

echo "==> API Python venv"
python3 -m venv "$BACKEND/venv"
# shellcheck disable=SC1091
source "$BACKEND/venv/bin/activate"
pip install -U pip wheel
pip install -r "$BACKEND/requirements.txt"

echo "==> FaceFusion clone + venv-ff"
if [[ ! -f "$FF/facefusion.py" ]]; then
  git clone --depth 1 https://github.com/facefusion/facefusion.git "$FF"
fi
python3 -m venv "$VENV_FF"
# shellcheck disable=SC1091
source "$VENV_FF/bin/activate"
pip install -U pip wheel
pip install -r "$FF/requirements.txt" "onnxruntime==1.24.4" imageio-ffmpeg
mkdir -p "$BACKEND/bin"
FF_EXE="$("$VENV_FF/bin/python" -c "import imageio_ffmpeg; print(imageio_ffmpeg.get_ffmpeg_exe())")"
ln -sf "$FF_EXE" "$BACKEND/bin/ffmpeg"
deactivate

echo "==> Download swap models (~2–4 GB)"
export FACEFUSION_PYTHON="$VENV_FF/bin/python"
export PATH="$BACKEND/bin:$PATH"
"$FACEFUSION_PYTHON" "$BACKEND/scripts/download_swap_models.py"

echo "==> Frontend -> backend/static"
bash "$ROOT/scripts/build_frontend.sh"

ENV_FILE="$BACKEND/.env"
touch "$ENV_FILE"
if ! grep -q '^FACEFUSION_PYTHON=' "$ENV_FILE" 2>/dev/null; then
  echo "FACEFUSION_PYTHON=venv-ff/bin/python" >> "$ENV_FILE"
fi

echo ""
echo "Setup complete."
echo "  1. Add Cloudinary keys to $ENV_FILE"
echo "  2. bash start.sh"
echo "  3. Configure nginx: deploy/nginx/face-swap.conf"
