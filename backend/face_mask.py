import os
import sys
import types

import cv2
import numpy as np
import torch
from torchvision.transforms.functional import normalize

from download_utils import ensure_parsenet_weights


def _patch_torchvision_compat():
    name = "torchvision.transforms.functional_tensor"
    if name in sys.modules:
        return
    from torchvision.transforms import functional as tv_functional

    mod = types.ModuleType(name)
    mod.rgb_to_grayscale = tv_functional.rgb_to_grayscale
    sys.modules[name] = mod


_patch_torchvision_compat()

from basicsr.utils import img2tensor
from facexlib.parsing import init_parsing_model

_PARSE_FACE = [1, 2, 3, 4, 5, 6, 10, 11, 12, 13]
_HAIR = 17
_HAT = 18

_parser = None
_parser_failed = False
_device = torch.device("cpu")


def get_parser():
    global _parser, _parser_failed
    if _parser_failed:
        return None
    if _parser is None:
        try:
            ensure_parsenet_weights()
            _parser = init_parsing_model(
                model_name="parsenet",
                device=_device,
                model_rootpath="facexlib/weights",
            )
        except Exception as exc:
            _parser_failed = True
            print(f"Face parser unavailable: {exc}")
            return None
    return _parser


def _parse_labels(face_bgr: np.ndarray, size: int = 512) -> np.ndarray | None:
    h, w = face_bgr.shape[:2]
    parser = get_parser()
    if parser is None:
        return None
    resized = cv2.resize(face_bgr, (size, size), interpolation=cv2.INTER_LINEAR)
    tensor = img2tensor(resized.astype(np.float32) / 255.0, bgr2rgb=True, float32=True)
    normalize(tensor, (0.5, 0.5, 0.5), (0.5, 0.5, 0.5), inplace=True)
    tensor = tensor.unsqueeze(0).to(_device)
    with torch.no_grad():
        logits = parser(tensor)[0]
        labels = logits.argmax(dim=1).squeeze().cpu().numpy()
    return cv2.resize(labels.astype(np.float32), (w, h), interpolation=cv2.INTER_NEAREST)


def chin_beard_score(crop_bgr: np.ndarray) -> float:
    h, w = crop_bgr.shape[:2]
    lower = crop_bgr[int(h * 0.55) :, :]
    if lower.size == 0:
        return 0.0
    gray = cv2.cvtColor(lower, cv2.COLOR_BGR2GRAY)
    return float((gray < 100).mean())


def beard_mismatch(source_crop: np.ndarray, target_crop: np.ndarray) -> bool:
    return chin_beard_score(source_crop) > 0.14 and chin_beard_score(target_crop) < 0.11
