import os
import time
from typing import Any

import cloudinary
import cloudinary.api
import cloudinary.uploader
from dotenv import load_dotenv

load_dotenv()

TEMPLATE_FOLDER = "face-swap/templates"
RESULT_FOLDER = "face-swap/results"
MAX_TEMPLATES = 6

_configured = False


def _configure() -> None:
    global _configured
    if _configured:
        return

    cloud_name = os.getenv("CLOUDINARY_CLOUD_NAME")
    api_key = os.getenv("CLOUDINARY_API_KEY")
    api_secret = os.getenv("CLOUDINARY_API_SECRET")

    if not all([cloud_name, api_key, api_secret]):
        raise RuntimeError(
            "Cloudinary credentials missing. Set CLOUDINARY_CLOUD_NAME, "
            "CLOUDINARY_API_KEY, and CLOUDINARY_API_SECRET in backend/.env"
        )

    cloudinary.config(
        cloud_name=cloud_name,
        api_key=api_key,
        api_secret=api_secret,
        secure=True,
    )
    _configured = True


def is_configured() -> bool:
    return bool(
        os.getenv("CLOUDINARY_CLOUD_NAME")
        and os.getenv("CLOUDINARY_API_KEY")
        and os.getenv("CLOUDINARY_API_SECRET")
    )


def clear_all_templates() -> int:
    """Remove every template in Cloudinary (fresh start on deploy)."""
    if not is_configured():
        return 0
    _configure()
    deleted = 0
    next_cursor = None
    prefix = f"{TEMPLATE_FOLDER}/"
    while True:
        kwargs: dict[str, Any] = {
            "type": "upload",
            "prefix": prefix,
            "max_results": 100,
        }
        if next_cursor:
            kwargs["next_cursor"] = next_cursor
        response = cloudinary.api.resources(**kwargs)
        ids = [item["public_id"] for item in response.get("resources", [])]
        if ids:
            result = cloudinary.api.delete_resources(ids, resource_type="image")
            for status in result.get("deleted", {}).values():
                if status == "deleted":
                    deleted += 1
        next_cursor = response.get("next_cursor")
        if not next_cursor:
            break
    return deleted


def list_templates() -> list[dict[str, Any]]:
    _configure()
    response = cloudinary.api.resources(
        type="upload",
        prefix=f"{TEMPLATE_FOLDER}/",
        max_results=MAX_TEMPLATES,
        direction="desc",
    )
    templates = []
    for item in response.get("resources", []):
        templates.append(
            {
                "id": item["public_id"],
                "url": item["secure_url"],
                "width": item.get("width"),
                "height": item.get("height"),
                "created_at": item.get("created_at"),
            }
        )
    templates.sort(key=lambda t: t.get("created_at") or "")
    return templates


def count_templates() -> int:
    return len(list_templates())


def upload_template(file_bytes: bytes, filename: str) -> dict[str, Any]:
    _configure()
    if count_templates() >= MAX_TEMPLATES:
        raise ValueError(f"Maximum {MAX_TEMPLATES} template images allowed")

    safe_name = os.path.splitext(filename or "template")[0].replace(" ", "-")[:40]
    public_id = f"{safe_name}-{int(time.time())}"
    result = cloudinary.uploader.upload(
        file_bytes,
        folder=TEMPLATE_FOLDER,
        public_id=public_id,
        overwrite=False,
        resource_type="image",
        format="jpg",
    )
    return {
        "id": result["public_id"],
        "url": result["secure_url"],
        "width": result.get("width"),
        "height": result.get("height"),
    }


def delete_template(public_id: str) -> None:
    _configure()
    if not public_id.startswith(TEMPLATE_FOLDER):
        raise ValueError("Invalid template id")
    cloudinary.uploader.destroy(public_id, resource_type="image")


def upload_result_bytes(file_bytes: bytes) -> dict[str, Any]:
    """Upload swap result from memory — nothing written to disk."""
    _configure()
    public_id = f"swap-{int(time.time())}"
    result = cloudinary.uploader.upload(
        file_bytes,
        folder=RESULT_FOLDER,
        public_id=public_id,
        resource_type="image",
        format="jpg",
    )
    return {
        "id": result["public_id"],
        "url": result["secure_url"],
        "width": result.get("width"),
        "height": result.get("height"),
    }
