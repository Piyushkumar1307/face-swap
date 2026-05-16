import cv2
import numpy as np


def _scale_faces(faces, scale: float):
    if scale == 1.0:
        return faces
    for face in faces:
        face.bbox = face.bbox / scale
        if face.kps is not None:
            face.kps = face.kps / scale
    return faces


def _offset_faces(faces, dx: float, dy: float):
    for face in faces:
        face.bbox = face.bbox - np.array([dx, dy, dx, dy], dtype=np.float32)
        if face.kps is not None:
            face.kps[:, 0] -= dx
            face.kps[:, 1] -= dy
    return faces


def detect_faces(app_face, img: np.ndarray) -> list:
    """
    Detect faces with retries for rotated EXIF-fixed images, padding, and resize.
    """
    if img is None or img.size == 0:
        return []

    faces = app_face.get(img)
    if faces:
        return faces

    h, w = img.shape[:2]

    # Tight portrait crops: add border so detector sees full head context
    pad = max(int(min(h, w) * 0.12), 24)
    padded = cv2.copyMakeBorder(img, pad, pad, pad, pad, cv2.BORDER_REPLICATE)
    faces = app_face.get(padded)
    if faces:
        return _offset_faces(faces, pad, pad)

    # Very large images: face can be relatively small for det_size
    if max(h, w) > 1400:
        scale = 1280 / max(h, w)
        nw, nh = int(w * scale), int(h * scale)
        resized = cv2.resize(img, (nw, nh), interpolation=cv2.INTER_AREA)
        faces = app_face.get(resized)
        if faces:
            return _scale_faces(faces, scale)

    # Small images: upscale for detection
    if max(h, w) < 480:
        scale = 640 / max(h, w)
        nw, nh = int(w * scale), int(h * scale)
        resized = cv2.resize(img, (nw, nh), interpolation=cv2.INTER_LANCZOS4)
        faces = app_face.get(resized)
        if faces:
            return _scale_faces(faces, scale)

    return []
