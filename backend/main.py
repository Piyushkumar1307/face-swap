import threading
from pathlib import Path

import certifi
import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from cloudinary_service import (
    delete_template,
    is_configured,
    list_templates,
    upload_result_bytes,
    upload_template,
)
from facefusion_runner import (
    ensure_swap_models_downloaded,
    is_facefusion_ready,
    models_download_in_progress,
    perform_swap,
    readiness_status,
    swap_models_installed,
)
from image_utils import bytes_to_bgr, bgr_to_jpeg_bytes

load_dotenv()

BACKEND_DIR = Path(__file__).resolve().parent
STATIC_DIR = BACKEND_DIR / "static"

app = FastAPI(title="Face Swap API (FaceFusion)")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _bootstrap_models() -> None:
    if swap_models_installed():
        print("FaceFusion models present.")
        return
    print("FaceFusion models missing — downloading in background (API stays up)...")
    if ensure_swap_models_downloaded():
        print("FaceFusion models ready.")
    else:
        print("WARNING: FaceFusion model download failed or incomplete.")


@app.on_event("startup")
def check_facefusion():
    status = readiness_status()
    if is_facefusion_ready():
        print("FaceFusion ready.")
        return
    if not status["script"]:
        print("WARNING: FaceFusion is not installed. Run: bash scripts/setup_facefusion.sh")
        return
    if not status["models"]:
        threading.Thread(target=_bootstrap_models, daemon=True).start()
        return
    print("WARNING: FaceFusion is not ready (check ffmpeg / python).")


async def load_image_from_url(url: str):
    async with httpx.AsyncClient(timeout=30.0, verify=certifi.where(), follow_redirects=True) as client:
        response = await client.get(url)
        response.raise_for_status()
    content_type = response.headers.get("content-type", "")
    if content_type and "image" not in content_type and "octet-stream" not in content_type:
        raise HTTPException(
            status_code=400,
            detail="Template URL did not return an image. Re-upload the template.",
        )
    img = bytes_to_bgr(response.content)
    if img is None or img.size == 0:
        raise HTTPException(
            status_code=400,
            detail="Could not read template image. Try uploading the template again.",
        )
    return img


def run_swap(source_img, target_img):
    if models_download_in_progress():
        raise HTTPException(
            status_code=503,
            detail="FaceFusion models are downloading. Retry in a few minutes.",
        )
    if not is_facefusion_ready():
        status = readiness_status()
        if not status["models"]:
            raise HTTPException(
                status_code=503,
                detail="FaceFusion models are not installed yet. Wait for download to finish.",
            )
        raise HTTPException(
            status_code=503,
            detail=(
                "FaceFusion is not installed. On the server run: "
                "bash backend/scripts/setup_facefusion.sh"
            ),
        )
    try:
        return perform_swap(source_img, target_img)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/health")
def api_health():
    status = readiness_status()
    return {
        "message": "Face Swap API Running (FaceFusion)",
        "cloudinary": is_configured(),
        "facefusion": is_facefusion_ready(),
        "models_downloading": models_download_in_progress(),
        "models_installed": bool(status["models"]),
        "storage": "cloudinary",
    }


@app.get("/templates")
def get_templates():
    if not is_configured():
        raise HTTPException(
            status_code=503,
            detail="Cloudinary is not configured on the server",
        )
    try:
        return {"templates": list_templates()}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/templates")
async def add_template(file: UploadFile = File(...)):
    if not is_configured():
        raise HTTPException(status_code=503, detail="Cloudinary is not configured")
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image")

    data = await file.read()
    try:
        template = upload_template(data, file.filename or "template")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return template


@app.delete("/templates/{public_id:path}")
def remove_template(public_id: str):
    if not is_configured():
        raise HTTPException(status_code=503, detail="Cloudinary is not configured")
    try:
        delete_template(public_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {"ok": True}


@app.post("/swap-face")
async def swap_face(
    source: UploadFile = File(...),
    target_url: str = Form(...),
):
    if not is_configured():
        raise HTTPException(status_code=503, detail="Cloudinary is not configured")

    source_bytes = await source.read()
    source_img = bytes_to_bgr(source_bytes)
    if source_img is None:
        raise HTTPException(status_code=400, detail="Invalid source image")

    target_img = await load_image_from_url(target_url)
    result = run_swap(source_img, target_img)

    try:
        uploaded = upload_result_bytes(bgr_to_jpeg_bytes(result))
    except ValueError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Upload failed: {exc}") from exc

    return {
        "url": uploaded["url"],
        "width": uploaded.get("width"),
        "height": uploaded.get("height"),
        "id": uploaded.get("id"),
    }


def _mount_frontend() -> None:
    index = STATIC_DIR / "index.html"
    if not index.is_file():
        print("No frontend build in static/ — API only (run scripts/build_frontend.sh).")
        return

    assets_dir = STATIC_DIR / "assets"
    if assets_dir.is_dir():
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    @app.get("/", include_in_schema=False)
    async def spa_index():
        return FileResponse(index)

    @app.get("/{spa_path:path}", include_in_schema=False)
    async def spa_fallback(spa_path: str):
        # API routes are registered above; this only serves static files + SPA fallback.
        if spa_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="Not Found")
        file_path = STATIC_DIR / spa_path
        if file_path.is_file():
            return FileResponse(file_path)
        return FileResponse(index)

    print(f"Serving UI from {STATIC_DIR}")


_mount_frontend()
