import cv2
import numpy as np


def match_skin_tone(
    swapped: np.ndarray,
    target_crop: np.ndarray,
    mask: np.ndarray,
) -> np.ndarray:
    """Match swapped face colors to the template skin tone in LAB space."""
    m = mask > 0.25
    if m.sum() < 50:
        return swapped

    src = cv2.cvtColor(swapped, cv2.COLOR_BGR2LAB).astype(np.float32)
    ref = cv2.cvtColor(target_crop, cv2.COLOR_BGR2LAB).astype(np.float32)

    for channel in range(3):
        src_vals = src[:, :, channel][m]
        ref_vals = ref[:, :, channel][m]
        src_mean, src_std = src_vals.mean(), src_vals.std() + 1e-5
        ref_mean, ref_std = ref_vals.mean(), ref_vals.std() + 1e-5
        src[:, :, channel] = (src[:, :, channel] - src_mean) * (ref_std / src_std) + ref_mean

    matched = cv2.cvtColor(np.clip(src, 0, 255).astype(np.uint8), cv2.COLOR_LAB2BGR)
    return matched
