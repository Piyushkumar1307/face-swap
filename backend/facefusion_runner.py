"""Run FaceFusion headless for production-quality face swaps (free, open source)."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
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
DEBUG_LOG = BACKEND_DIR.parent / ".cursor" / "debug-d365c7.log"
DEBUG_SESSION = "d365c7"

_models_download_lock = threading.Lock()
_models_downloading = False


def _swap_model_name() -> str:
    return os.environ.get("FACEFUSION_SWAP_MODEL", "hyperswap_1a_256")


def _enhancer_model_name() -> str:
    return os.environ.get("FACEFUSION_ENHANCER_MODEL", "gfpgan_1.4")


def required_model_paths() -> list[Path]:
    models_dir = FACEFUSION_DIR / ".assets" / "models"
    paths = [models_dir / f"{_swap_model_name()}.onnx"]
    processors = os.environ.get("FACEFUSION_PROCESSORS", "face_swapper face_enhancer").split()
    if "face_enhancer" in processors:
        paths.append(models_dir / f"{_enhancer_model_name()}.onnx")
    return paths


def swap_models_installed() -> bool:
    return all(path.is_file() and path.stat().st_size > 0 for path in required_model_paths())


# region agent log
def _debug_log(hypothesis_id: str, message: str, data: dict | None = None) -> None:
    try:
        payload = {
            "sessionId": DEBUG_SESSION,
            "hypothesisId": hypothesis_id,
            "location": "facefusion_runner.py",
            "message": message,
            "data": data or {},
            "timestamp": int(time.time() * 1000),
        }
        DEBUG_LOG.parent.mkdir(parents=True, exist_ok=True)
        with DEBUG_LOG.open("a", encoding="utf-8") as f:
            f.write(json.dumps(payload) + "\n")
    except OSError:
        pass


# endregion


def readiness_status() -> dict[str, bool | list[str]]:
    """Cheap checks used by / and startup (no subprocess --version)."""
    python_bin = Path(_facefusion_python())
    env = _ffmpeg_env()
    ffmpeg_ok = shutil.which("ffmpeg", path=env.get("PATH")) is not None
    missing_models = [str(p) for p in required_model_paths() if not p.is_file()]
    return {
        "script": FACEFUSION_SCRIPT.is_file(),
        "python": python_bin.is_file(),
        "ffmpeg": ffmpeg_ok,
        "models": len(missing_models) == 0,
        "missing_models": missing_models,
    }


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
        path = path.resolve()
        if path.is_file():
            return str(path)
    venv_ff = BACKEND_DIR / "venv-ff" / "bin" / "python"
    if venv_ff.is_file():
        return str(venv_ff)
    return sys.executable


def is_facefusion_ready() -> bool:
    status = readiness_status()
    ready = all(
        status[key]
        for key in ("script", "python", "ffmpeg", "models")
    )
    # region agent log
    if not ready:
        _debug_log("H8", "facefusion not ready", {"status": status})
    # endregion
    return ready


def models_download_in_progress() -> bool:
    return _models_downloading


def ensure_swap_models_downloaded() -> bool:
    """Download swap models if missing. Returns True when models are on disk."""
    global _models_downloading
    if swap_models_installed():
        return True

    with _models_download_lock:
        if swap_models_installed():
            return True
        _models_downloading = True
        # region agent log
        _debug_log("H9", "starting background model download", {"missing": readiness_status().get("missing_models")})
        # endregion
        try:
            script = BACKEND_DIR / "scripts" / "download_swap_models.py"
            proc = subprocess.run(
                [sys.executable, str(script)],
                cwd=BACKEND_DIR,
                env=_ffmpeg_env(),
                timeout=int(os.environ.get("FACEFUSION_DOWNLOAD_TIMEOUT_SEC", "3600")),
            )
            ok = proc.returncode == 0 and swap_models_installed()
            # region agent log
            _debug_log(
                "H9",
                "model download finished",
                {"ok": ok, "returncode": proc.returncode, "installed": swap_models_installed()},
            )
            # endregion
            return ok
        except (OSError, subprocess.TimeoutExpired) as exc:
            _debug_log("H9", "model download failed", {"error": type(exc).__name__})
            return False
        finally:
            _models_downloading = False


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
    if not is_facefusion_ready():
        status = readiness_status()
        if not status["models"]:
            raise RuntimeError(
                "FaceFusion models are still downloading. Retry in a few minutes."
            )
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
