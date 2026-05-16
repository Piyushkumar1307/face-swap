import cv2
import numpy as np

from face_mask import _parse_labels


def _inner_swap_zone_crop(kps: np.ndarray, h: int, w: int) -> np.ndarray:
    """Eyes, nose, mouth — swap MUST show here."""
    le, re, nose, lm, rm = kps.astype(np.float32)
    eye_y = (le[1] + re[1]) * 0.5
    mouth_y = (lm[1] + rm[1]) * 0.5
    eye_dist = float(np.linalg.norm(re - le)) + 1e-5
    center_x = (le[0] + re[0]) * 0.5

    top_y = eye_y - eye_dist * 0.05
    chin_y = mouth_y + eye_dist * 0.35

    mask = np.zeros((h, w), np.float32)
    cv2.ellipse(
        mask,
        (int(center_x), int((top_y + chin_y) / 2)),
        (int(eye_dist * 0.92), int(max(chin_y - top_y, 6) * 0.58)),
        0,
        0,
        360,
        1.0,
        -1,
    )
    k = max(int(eye_dist * 0.08) | 1, 3)
    if k % 2 == 0:
        k += 1
    return cv2.GaussianBlur(mask, (k, k), 0)


def _hat_only_mask_crop(target_crop: np.ndarray, kps: np.ndarray) -> np.ndarray:
    """Only hard-hat pixels in the upper face — not the whole head."""
    h, w = target_crop.shape[:2]
    le, re, nose, _, _ = kps.astype(np.float32)
    eye_y = (le[1] + re[1]) * 0.5
    nose_y = nose[1]

    labels = _parse_labels(target_crop, size=512)
    if labels is None:
        mask = np.zeros((h, w), np.float32)
        cutoff = int(max(eye_y - (nose_y - eye_y) * 0.3, 0))
        mask[:cutoff, :] = 1.0
        return mask

    # Hat class only (not hair); restricted above nose
    hat = (labels == 18).astype(np.float32)
    upper_limit = int(nose_y + (nose_y - eye_y) * 0.15)
    hat[upper_limit:, :] = 0.0

    k = max(min(h, w) // 32, 3)
    if k % 2 == 0:
        k += 1
    hat = cv2.erode(hat, np.ones((k, k), np.uint8), iterations=1)
    return hat


def build_preserve_mask(
    target_crop: np.ndarray,
    target_kps: np.ndarray,
    M: np.ndarray,
    full_h: int,
    full_w: int,
) -> np.ndarray:
    """Small regions to keep from template: mainly hard-hat brim, not the whole face."""
    ch, cw = target_crop.shape[:2]
    preserve = _hat_only_mask_crop(target_crop, target_kps)

    IM = cv2.invertAffineTransform(M)
    warped = cv2.warpAffine(preserve, IM, (full_w, full_h), flags=cv2.INTER_LINEAR, borderValue=0.0)

    swap_zone = _inner_swap_zone_crop(target_kps, ch, cw)
    swap_warped = cv2.warpAffine(swap_zone, IM, (full_w, full_h), flags=cv2.INTER_LINEAR, borderValue=0.0)

    # Never restore template over eyes/nose/mouth
    warped = np.where(swap_warped > 0.2, np.minimum(warped, 0.18), warped)

    k = max(min(full_h, full_w) // 50, 7)
    if k % 2 == 0:
        k += 1
    warped = cv2.GaussianBlur(warped, (k, k), 0)
    return np.clip(warped, 0.0, 1.0)


def merge_template_and_swap(
    template_img: np.ndarray,
    swapped_img: np.ndarray,
    preserve_mask: np.ndarray,
    face_bbox: np.ndarray | None = None,
) -> np.ndarray:
    if face_bbox is not None:
        x1, y1, x2, y2 = face_bbox.astype(int)
        x1, y1 = max(0, x1), max(0, y1)
        roi = preserve_mask[y1:y2, x1:x2]
        if roi.size > 0 and float(roi.mean()) > 0.42:
            return swapped_img

    p = preserve_mask[:, :, np.newaxis]
    merged = p * template_img.astype(np.float32) + (1.0 - p) * swapped_img.astype(np.float32)
    return np.clip(merged, 0, 255).astype(np.uint8)
