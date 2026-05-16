import cv2
import numpy as np

from color_match import match_skin_tone
from face_mask import build_swap_mask, fallback_face_mask


def _mask_centroid(mask: np.ndarray) -> tuple[int, int]:
    ys, xs = np.where(mask > 0.35)
    if len(xs) == 0:
        h, w = mask.shape[:2]
        return w // 2, h // 2
    return int(np.mean(xs)), int(np.mean(ys))


def paste_face(
    target_img: np.ndarray,
    face_patch: np.ndarray,
    M: np.ndarray,
    target_crop: np.ndarray,
    target_kps: np.ndarray,
    source_crop: np.ndarray | None = None,
) -> np.ndarray:
    h, w = target_img.shape[:2]
    base = target_img.astype(np.float32)

    local_mask = build_swap_mask(
        face_patch,
        target_kps,
        source_crop=source_crop,
        target_crop=target_crop,
    )

    if local_mask.max() < 0.08:
        ch, cw = face_patch.shape[:2]
        local_mask = fallback_face_mask(ch, cw)

    face_patch = match_skin_tone(face_patch, target_crop, local_mask)

    IM = cv2.invertAffineTransform(M)
    warped_face = cv2.warpAffine(
        face_patch,
        IM,
        (w, h),
        flags=cv2.INTER_LANCZOS4,
        borderValue=0.0,
    )
    warped_mask = cv2.warpAffine(
        local_mask,
        IM,
        (w, h),
        flags=cv2.INTER_LINEAR,
        borderValue=0.0,
    )
    warped_mask = np.clip(warped_mask, 0.0, 1.0)

    if warped_mask.max() < 0.08:
        return target_img

    mask_u8 = (warped_mask * 255).astype(np.uint8)
    center = _mask_centroid(warped_mask)

    try:
        return cv2.seamlessClone(
            warped_face,
            target_img,
            mask_u8,
            center,
            cv2.NORMAL_CLONE,
        )
    except cv2.error:
        soft = warped_mask[:, :, np.newaxis]
        merged = soft * warped_face.astype(np.float32) + (1.0 - soft) * base
        return np.clip(merged, 0, 255).astype(np.uint8)
