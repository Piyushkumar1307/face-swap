import os

import certifi
import httpx

PARSENET_URL = (
    "https://github.com/xinntao/facexlib/releases/download/v0.2.2/parsing_parsenet.pth"
)
PARSENET_PATH = os.path.join("facexlib", "weights", "parsing_parsenet.pth")


def secure_download(url: str, dest: str) -> str:
    """Download a file using certifi CA bundle (fixes macOS Python SSL errors)."""
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    if os.path.isfile(dest) and os.path.getsize(dest) > 1_000_000:
        return dest

    print(f"Downloading {url} ...")
    with httpx.Client(verify=certifi.where(), timeout=120.0, follow_redirects=True) as client:
        response = client.get(url)
        response.raise_for_status()

    with open(dest, "wb") as f:
        f.write(response.content)

    print(f"Saved to {dest}")
    return dest


def ensure_parsenet_weights() -> str:
    return secure_download(PARSENET_URL, PARSENET_PATH)
