import cv2
import numpy as np
from insightface.utils import face_align

from composite import build_preserve_mask, merge_template_and_swap
from face_detect import detect_faces


def pick_largest_face(faces):
    if len(faces) == 1:
        return faces[0]
    return max(
        faces,
        key=lambda f: (f.bbox[2] - f.bbox[0]) * (f.bbox[3] - f.bbox[1]),
    )


def match_source_face(source_faces, target_face):
    if len(source_faces) == 1:
        return source_faces[0]

    target_emb = target_face.normed_embedding
    best_face = source_faces[0]
    best_score = -1.0

    for face in source_faces:
        score = float(np.dot(face.normed_embedding, target_emb))
        if score > best_score:
            best_score = score
            best_face = face

    return best_face


def upscale_if_faces_small(img, faces, min_ratio=0.15, max_scale=2.0):
    if not faces:
        return img, 1.0

    face = pick_largest_face(faces)
    bbox = face.bbox
    face_w = bbox[2] - bbox[0]
    ratio = face_w / img.shape[1]

    if ratio >= min_ratio:
        return img, 1.0

    scale = min(max_scale, min_ratio / ratio)
    new_w = int(img.shape[1] * scale)
    new_h = int(img.shape[0] * scale)
    upscaled = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_LANCZOS4)
    return upscaled, scale


def downscale(img, scale):
    if scale <= 1.0:
        return img
    new_w = int(img.shape[1] / scale)
    new_h = int(img.shape[0] / scale)
    return cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_LANCZOS4)


def swap_one(swapper, source_face, source_img, target_img, target_face):
    template_original = target_img.copy()
    h, w = target_img.shape[:2]

    crop_size = swapper.input_size[0]
    target_crop, M = face_align.norm_crop2(target_img, target_face.kps, crop_size)

    swapped = swapper.get(target_img, target_face, source_face, paste_back=True)

    diff = np.mean(np.abs(swapped.astype(np.float32) - template_original.astype(np.float32)))
    if diff < 4.0:
        raise ValueError(
            "Face swap produced no visible change. Try a clearer front-facing selfie."
        )

    preserve = build_preserve_mask(target_crop, target_face.kps, M, h, w)
    return merge_template_and_swap(
        template_original,
        swapped,
        preserve,
        face_bbox=target_face.bbox,
    )


def perform_swap(app_face, swapper, source_img, target_img):
    source_faces = detect_faces(app_face, source_img)
    target_faces = detect_faces(app_face, target_img)

    if not source_faces:
        raise ValueError(
            "No face found in your photo. Use a clear front-facing selfie with good lighting."
        )
    if not target_faces:
        raise ValueError(
            "No face found in the selected template. Use a template with a clear, visible face."
        )

    source_work, source_scale = upscale_if_faces_small(source_img, source_faces)
    target_work, target_scale = upscale_if_faces_small(target_img, target_faces)

    if source_scale > 1.0:
        source_faces = detect_faces(app_face, source_work)
    if target_scale > 1.0:
        target_faces = detect_faces(app_face, target_work)

    if not source_faces:
        raise ValueError("No face found in your photo after processing.")
    if not target_faces:
        raise ValueError("No face found in the template after processing.")

    target_faces = sorted(
        target_faces,
        key=lambda f: (f.bbox[2] - f.bbox[0]) * (f.bbox[3] - f.bbox[1]),
        reverse=True,
    )

    result = target_work.copy()
    for target_face in target_faces:
        source_face = match_source_face(source_faces, target_face)
        result = swap_one(swapper, source_face, source_work, result, target_face)

    return downscale(result, target_scale)
