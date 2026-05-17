#!/usr/bin/env python3
"""Download only models needed for face_swapper + face_enhancer (not all FaceFusion processors)."""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
FACEFUSION_DIR = BACKEND / "facefusion"
DEBUG_LOG = BACKEND.parent / ".cursor" / "debug-d365c7.log"
SESSION_ID = "d365c7"

SWAP_MODEL = os.environ.get("FACEFUSION_SWAP_MODEL", "hyperswap_1a_256")
ENHANCER_MODEL = os.environ.get("FACEFUSION_ENHANCER_MODEL", "gfpgan_1.4")

# Only download models our API actually uses (matches facefusion_runner defaults).
COMMON_MODEL_KEYS: dict[str, set[str] | None] = {
    "content_analyser": {"nsfw_1", "nsfw_2", "nsfw_3"},
    "face_classifier": {"fairface"},
    "face_detector": {"yolo_face"},
    "face_landmarker": {"2dfan4"},
    "face_masker": {"xseg_1", "bisenet_resnet_34"},
    "face_recognizer": {"arcface"},
}


# region agent log
def _log(hypothesis_id: str, message: str, data: dict | None = None) -> None:
    try:
        payload = {
            "sessionId": SESSION_ID,
            "hypothesisId": hypothesis_id,
            "location": "download_swap_models.py",
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


def _onnx_paths(model: dict) -> list[Path]:
    paths: list[Path] = []
    for source in model.get("sources", {}).values():
        rel = source.get("path", "")
        if rel.endswith(".onnx"):
            paths.append((FACEFUSION_DIR / rel).resolve())
    return paths


def _min_bytes_for(path: Path) -> int:
    name = path.name
    if name.startswith("xseg"):
        return 1_000_000
    if name.startswith("bisenet"):
        return 1_000_000
    if name.startswith("inswapper") or name.startswith("hyperswap"):
        return 50_000_000
    if name.startswith("gfpgan"):
        return 50_000_000
    return 10_000


def _files_valid(paths: list[Path]) -> bool:
    for path in paths:
        if not path.is_file():
            return False
        if path.stat().st_size < _min_bytes_for(path):
            print(f"[build] corrupt/incomplete model file ({path.stat().st_size} bytes): {path.name}", file=sys.stderr)
            path.unlink(missing_ok=True)
            for sibling in path.parent.glob(path.stem + ".*"):
                sibling.unlink(missing_ok=True)
            return False
    return True


def _download_model_entry(model: dict) -> bool:
    from facefusion.download import conditional_download_hashes, conditional_download_sources

    hashes = model.get("hashes")
    sources = model.get("sources")
    if not hashes or not sources:
        return True
    return bool(
        conditional_download_hashes(hashes) and conditional_download_sources(sources)
    )


def _download_model_entry_with_retry(model: dict, label: str, retries: int = 5) -> bool:
    for attempt in range(1, retries + 1):
        if _download_model_entry(model) and _files_valid(_onnx_paths(model)):
            return True
        print(f"[build] retry {label} ({attempt}/{retries})", file=sys.stderr)
        time.sleep(min(attempt * 3, 15))
    return False


def _download_model_set(model_set: dict, only_keys: set[str] | None = None) -> bool:
    for key, model in model_set.items():
        if key == "__metadata__" or not isinstance(model, dict):
            continue
        if only_keys is not None and key not in only_keys:
            continue
        if not _download_model_entry_with_retry(model, key):
            return False
    return True


def main() -> int:
    if not FACEFUSION_DIR.is_dir():
        _log("H2", "facefusion dir missing", {"path": str(FACEFUSION_DIR)})
        print("ERROR: facefusion directory not found", file=sys.stderr)
        return 1

    os.chdir(FACEFUSION_DIR)
    sys.path.insert(0, str(FACEFUSION_DIR))

    processors = os.environ.get("FACEFUSION_PROCESSORS", "face_swapper face_enhancer").split()
    print(f"[build] Selective download: swap={SWAP_MODEL} processors={processors}")
    # region agent log
    _log("H1", "start selective download", {"swap": SWAP_MODEL, "enhancer": ENHANCER_MODEL})
    # endregion

    from facefusion import content_analyser, face_classifier, face_detector, face_landmarker
    from facefusion import face_masker, face_recognizer, state_manager
    from facefusion.processors.modules.face_enhancer import core as face_enhancer_core
    from facefusion.processors.modules.face_swapper import core as face_swapper_core

    state_manager.init_item("download_providers", ["huggingface", "github"])
    state_manager.init_item("download_scope", "lite")
    state_manager.init_item("log_level", "info")

    common = [
        content_analyser,
        face_classifier,
        face_detector,
        face_landmarker,
        face_masker,
        face_recognizer,
    ]

    for module in common:
        name = module.__name__.split(".")[-1]
        only = COMMON_MODEL_KEYS.get(name)
        # region agent log
        _log("H3", "downloading common module", {"module": name, "keys": sorted(only) if only else "all"})
        # endregion
        model_set = module.create_static_model_set("lite")
        if not _download_model_set(model_set, only):
            _log("H3", "common module download failed", {"module": name})
            print(f"ERROR: failed downloading {name}", file=sys.stderr)
            return 1

    swap_set = face_swapper_core.create_static_model_set("lite")
    if SWAP_MODEL not in swap_set:
        print(f"ERROR: unknown swap model {SWAP_MODEL}", file=sys.stderr)
        return 1
    # region agent log
    _log("H4", "downloading face_swapper model only", {"model": SWAP_MODEL})
    # endregion
    if not _download_model_set(swap_set, {SWAP_MODEL}):
        print(f"ERROR: failed downloading swap model {SWAP_MODEL}", file=sys.stderr)
        return 1

    processors = os.environ.get("FACEFUSION_PROCESSORS", "face_swapper face_enhancer").split()
    if "face_enhancer" in processors:
        enh_set = face_enhancer_core.create_static_model_set("lite")
        if ENHANCER_MODEL not in enh_set:
            print(f"ERROR: unknown enhancer model {ENHANCER_MODEL}", file=sys.stderr)
            return 1
        # region agent log
        _log("H4", "downloading face_enhancer model only", {"model": ENHANCER_MODEL})
        # endregion
        if not _download_model_set(enh_set, {ENHANCER_MODEL}):
            print(f"ERROR: failed downloading enhancer {ENHANCER_MODEL}", file=sys.stderr)
            return 1
    else:
        print("[build] Skipping face_enhancer download (not in FACEFUSION_PROCESSORS)")

    required_files = [FACEFUSION_DIR / ".assets/models" / f"{SWAP_MODEL}.onnx"]
    if "face_enhancer" in os.environ.get("FACEFUSION_PROCESSORS", "face_swapper face_enhancer").split():
        required_files.append(FACEFUSION_DIR / ".assets/models" / f"{ENHANCER_MODEL}.onnx")
    missing = [str(p) for p in required_files if not p.is_file()]
    if missing:
        _log("H7", "required model files missing after download", {"missing": missing})
        print(f"ERROR: missing model files: {missing}", file=sys.stderr)
        return 1

    # region agent log
    _log("H1", "selective download complete", {"verified": [p.name for p in required_files]})
    # endregion
    print("[build] Swap models downloaded successfully.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
