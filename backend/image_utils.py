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


def bgr_to_jpeg_bytes(image_bgr: np.ndarray, quality: int = 95) -> bytes:
    ok, encoded = cv2.imencode(".jpg", image_bgr, [cv2.IMWRITE_JPEG_QUALITY, quality])
    if not ok:
        raise ValueError("Failed to encode result image")
    return encoded.tobytes()
