#!/usr/bin/env bash
# Install FaceFusion + bundled ffmpeg for the face-swap API (no Homebrew required).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
FF_DIR="$ROOT/facefusion"
VENV="$ROOT/venv-ff"
BIN_DIR="$ROOT/bin"

if [[ ! -d "$FF_DIR" ]]; then
  echo "Cloning FaceFusion..."
  git clone --depth 1 https://github.com/facefusion/facefusion.git "$FF_DIR"
fi

echo "Creating FaceFusion virtualenv at $VENV ..."
python3 -m venv "$VENV"
# shellcheck disable=SC1091
source "$VENV/bin/activate"

pip install -U pip wheel
pip install -r "$FF_DIR/requirements.txt"
pip install "onnxruntime==1.24.4"
pip install imageio-ffmpeg

mkdir -p "$BIN_DIR"
FF_EXE="$("$VENV/bin/python" -c "import imageio_ffmpeg; print(imageio_ffmpeg.get_ffmpeg_exe())")"
ln -sf "$FF_EXE" "$BIN_DIR/ffmpeg"
echo "Bundled ffmpeg: $FF_EXE"

cd "$FF_DIR"
export PATH="$BIN_DIR:$PATH"
echo "Downloading FaceFusion models (first run may take several minutes)..."
"$VENV/bin/python" facefusion.py force-download --log-level info

deactivate

ENV_FILE="$ROOT/.env"
touch "$ENV_FILE"
if ! grep -q '^FACEFUSION_PYTHON=' "$ENV_FILE" 2>/dev/null; then
  echo "FACEFUSION_PYTHON=$VENV/bin/python" >> "$ENV_FILE"
  echo "Added FACEFUSION_PYTHON to $ENV_FILE"
fi

echo ""
echo "FaceFusion setup complete. Restart the API:"
echo "  cd $ROOT && source venv/bin/activate && uvicorn main:app --reload"
