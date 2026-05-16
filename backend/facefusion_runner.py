"""Run FaceFusion headless for production-quality face swaps (free, open source)."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import uuid
from pathlib import Path

import cv2
import numpy as np

BACKEND_DIR = Path(__file__).resolve().parent
FACEFUSION_DIR = BACKEND_DIR / "facefusion"
FACEFUSION_SCRIPT = FACEFUSION_DIR / "facefusion.py"
JOBS_DIR = BACKEND_DIR / "facefusion_jobs"
WORK_ROOT = BACKEND_DIR / "facefusion_work"
FFMPEG_BIN_DIR = BACKEND_DIR / "bin"


def _bundled_ffmpeg_dir() -> str | None:
    """imageio-ffmpeg ships a static ffmpeg binary (no Homebrew required)."""
    try:
        import imageio_ffmpeg

        exe = imageio_ffmpeg.get_ffmpeg_exe()
        if exe and Path(exe).is_file():
            return str(Path(exe).parent)
    except ImportError:
        pass
    local = FFMPEG_BIN_DIR / "ffmpeg"
    if local.is_file():
        return str(FFMPEG_BIN_DIR)
    return None


def _ffmpeg_env() -> dict[str, str]:
    env = os.environ.copy()
    extra = _bundled_ffmpeg_dir()
    if extra:
        env["PATH"] = extra + os.pathsep + env.get("PATH", "")
    return env


def _facefusion_python() -> str:
    env = os.environ.get("FACEFUSION_PYTHON", "").strip()
    if env:
        path = Path(env).expanduser()
        if not path.is_absolute():
            path = BACKEND_DIR / path
        return str(path.resolve())
    venv_ff = BACKEND_DIR / "venv-ff" / "bin" / "python"
    if venv_ff.is_file():
        return str(venv_ff)
    return sys.executable


def is_facefusion_ready() -> bool:
    if not FACEFUSION_SCRIPT.is_file():
        return False
    python_bin = Path(_facefusion_python())
    if not python_bin.is_file():
        return False
    env = _ffmpeg_env()
    if shutil.which("ffmpeg", path=env.get("PATH")) is None:
        return False
    try:
        proc = subprocess.run(
            [str(python_bin), str(FACEFUSION_SCRIPT), "--version"],
            capture_output=True,
            text=True,
            cwd=FACEFUSION_DIR,
            env=env,
            timeout=120,
        )
        return proc.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def _require_ffmpeg() -> None:
    env = _ffmpeg_env()
    if shutil.which("ffmpeg", path=env.get("PATH")) is None:
        raise RuntimeError(
            "ffmpeg not found. Run: bash backend/scripts/setup_facefusion.sh"
        )


def _build_swap_command(source_path: Path, target_path: Path, output_path: Path, work_dir: Path) -> list[str]:
    processors = os.environ.get("FACEFUSION_PROCESSORS", "face_swapper face_enhancer").split()
    swap_model = os.environ.get("FACEFUSION_SWAP_MODEL", "hyperswap_1a_256")
    pixel_boost = os.environ.get("FACEFUSION_PIXEL_BOOST", "512x512")
    swap_weight = os.environ.get("FACEFUSION_SWAP_WEIGHT", "0.85")
    enhancer = os.environ.get("FACEFUSION_ENHANCER_MODEL", "gfpgan_1.4")
    enhancer_blend = os.environ.get("FACEFUSION_ENHANCER_BLEND", "80")
    detector_score = os.environ.get("FACEFUSION_DETECTOR_SCORE", "0.4")
    log_level = os.environ.get("FACEFUSION_LOG_LEVEL", "info")

    execution_providers = os.environ.get("FACEFUSION_EXECUTION_PROVIDERS", "").split()
    execution_providers = [p for p in execution_providers if p]

    cmd = [
        _facefusion_python(),
        str(FACEFUSION_SCRIPT),
        "headless-run",
        "--jobs-path",
        str(JOBS_DIR),
        "--temp-path",
        str(work_dir / "tmp"),
        "--processors",
        *processors,
        "-s",
        str(source_path),
        "-t",
        str(target_path),
        "-o",
        str(output_path),
        "--face-swapper-model",
        swap_model,
        "--face-swapper-pixel-boost",
        pixel_boost,
        "--face-swapper-weight",
        swap_weight,
        "--face-enhancer-model",
        enhancer,
        "--face-enhancer-blend",
        enhancer_blend,
        "--face-detector-model",
        "yolo_face",
        "--face-detector-score",
        detector_score,
        "--face-selector-mode",
        "reference",
        "--face-selector-order",
        "large-small",
        "--face-mask-types",
        "box",
        "occlusion",
        "region",
        "--output-image-quality",
        os.environ.get("FACEFUSION_OUTPUT_QUALITY", "95"),
        "--log-level",
        log_level,
    ]

    if execution_providers:
        cmd.extend(["--execution-providers", *execution_providers])

    return cmd


def _parse_stderr(proc: subprocess.CompletedProcess) -> str:
    text = (proc.stderr or proc.stdout or "").strip()
    if not text:
        return "FaceFusion failed with no error output."
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    for line in reversed(lines):
        lower = line.lower()
        if (
            "error" in lower
            or "failed" in lower
            or "no face" in lower
            or "facefusion" in lower
            or "match the target" in lower
        ):
            return line
    return lines[-1] if lines else "FaceFusion failed."


def perform_swap(source_bgr: np.ndarray, target_bgr: np.ndarray) -> np.ndarray:
    """Swap source identity onto target using FaceFusion."""
    _require_ffmpeg()
    if not FACEFUSION_SCRIPT.is_file():
        raise RuntimeError(
            "FaceFusion is not installed. Run: bash backend/scripts/setup_facefusion.sh"
        )

    JOBS_DIR.mkdir(parents=True, exist_ok=True)
    WORK_ROOT.mkdir(parents=True, exist_ok=True)

    work_dir = WORK_ROOT / uuid.uuid4().hex[:12]
    work_dir.mkdir(parents=True)

    source_path = work_dir / "source.jpg"
    target_path = work_dir / "target.jpg"
    # FaceFusion requires target and output to share the same extension
    output_path = work_dir / f"result{target_path.suffix}"

    try:
        if not cv2.imwrite(str(source_path), source_bgr):
            raise ValueError("Could not write source image for processing.")
        if not cv2.imwrite(str(target_path), target_bgr):
            raise ValueError("Could not write target image for processing.")

        cmd = _build_swap_command(source_path, target_path, output_path, work_dir)
        timeout = int(os.environ.get("FACEFUSION_TIMEOUT_SEC", "600"))

        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=FACEFUSION_DIR,
            env=_ffmpeg_env(),
            timeout=timeout,
        )

        if proc.returncode != 0:
            detail = _parse_stderr(proc)
            if re.search(r"no face", detail, re.I):
                raise ValueError(
                    "No face detected. Use a clear front-facing photo and a template with a visible face."
                )
            raise RuntimeError(detail)

        if not output_path.is_file():
            raise RuntimeError("FaceFusion finished but did not create an output image.")

        result = cv2.imread(str(output_path))
        if result is None or result.size == 0:
            raise RuntimeError("Could not read FaceFusion output image.")
        return result
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)
