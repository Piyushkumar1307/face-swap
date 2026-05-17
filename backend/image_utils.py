import io

import cv2
import numpy as np
from PIL import Image, ImageOps


def bytes_to_bgr(data: bytes) -> np.ndarray | None:
    """Decode image bytes with EXIF orientation fix (phones often save rotated pixels)."""
    if not data:
        return None
    try:
        pil = Image.open(io.BytesIO(data))
        pil = ImageOps.exif_transpose(pil)
        if pil.mode == "RGBA":
            background = Image.new("RGB", pil.size, (255, 255, 255))
            background.paste(pil, mask=pil.split()[3])
            pil = background
        elif pil.mode != "RGB":
            pil = pil.convert("RGB")
        rgb = np.array(pil)
        return cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
    except Exception:
        arr = np.frombuffer(data, dtype=np.uint8)
        return cv2.imdecode(arr, cv2.IMREAD_COLOR)


def limit_image_size(image_bgr: np.ndarray, max_edge: int = 1280) -> np.ndarray:
    """Downscale large photos before swap to reduce RAM use on small servers."""
    if image_bgr is None or image_bgr.size == 0:
        return image_bgr
    h, w = image_bgr.shape[:2]
    longest = max(h, w)
    if longest <= max_edge:
        return image_bgr
    scale = max_edge / longest
    new_w = max(1, int(w * scale))
    new_h = max(1, int(h * scale))
    return cv2.resize(image_bgr, (new_w, new_h), interpolation=cv2.INTER_AREA)


def bgr_to_jpeg_bytes(image_bgr: np.ndarray, quality: int = 95) -> bytes:
    ok, encoded = cv2.imencode(".jpg", image_bgr, [cv2.IMWRITE_JPEG_QUALITY, quality])
    if not ok:
        raise ValueError("Failed to encode result image")
    return encoded.tobytes()
