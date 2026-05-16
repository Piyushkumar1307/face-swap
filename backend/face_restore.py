import sys
import types

import cv2
import numpy as np

GFPGAN_MODEL_URL = (
    "https://github.com/TencentARC/GFPGAN/releases/download/v1.3.4/GFPGANv1.4.pth"
)
ENHANCE_SIZE = 512

_restorer = None


def _patch_torchvision_compat():
    name = "torchvision.transforms.functional_tensor"
    if name in sys.modules:
        return
    from torchvision.transforms import functional as tv_functional

    mod = types.ModuleType(name)
    mod.rgb_to_grayscale = tv_functional.rgb_to_grayscale
    sys.modules[name] = mod


def get_restorer():
    global _restorer
    if _restorer is not None:
        return _restorer

    _patch_torchvision_compat()
    from gfpgan.utils import GFPGANer

    print("Loading GFPGAN model (first run downloads ~350MB)...")
    _restorer = GFPGANer(
        model_path=GFPGAN_MODEL_URL,
        upscale=1,
        arch="clean",
        channel_multiplier=2,
        bg_upsampler=None,
    )
    print("GFPGAN ready.")
    return _restorer


def enhance_face_crop(crop_bgr, restorer, weight: float = 0.38) -> np.ndarray:
    """Enhance a single aligned face crop; no second full-image paste."""
    _, restored_faces, _ = restorer.enhance(
        crop_bgr,
        has_aligned=True,
        paste_back=False,
        weight=weight,
    )
    if not restored_faces:
        return crop_bgr
    return restored_faces[0]


def try_get_restorer():
    try:
        return get_restorer()
    except Exception as exc:
        print(f"GFPGAN unavailable: {exc}")
        return None
