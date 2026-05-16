import certifi
import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from cloudinary_service import (
    delete_template,
    is_configured,
    list_templates,
    upload_result_bytes,
    upload_template,
)
from facefusion_runner import is_facefusion_ready, perform_swap
from image_utils import bytes_to_bgr, bgr_to_jpeg_bytes

load_dotenv()

app = FastAPI(title="Face Swap API (FaceFusion)")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def check_facefusion():
    if is_facefusion_ready():
        print("FaceFusion ready.")
    else:
        print(
            "WARNING: FaceFusion is not ready. Run: bash scripts/setup_facefusion.sh"
        )


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
    if not is_facefusion_ready():
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


@app.get("/")
def home():
    return {
        "message": "Face Swap API Running (FaceFusion)",
        "cloudinary": is_configured(),
        "facefusion": is_facefusion_ready(),
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
