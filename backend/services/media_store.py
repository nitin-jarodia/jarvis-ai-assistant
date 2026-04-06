from __future__ import annotations

import base64
import os
import uuid
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
MEDIA_ROOT = PROJECT_ROOT / "media"
UPLOADS_DIR = MEDIA_ROOT / "uploads"
GENERATED_DIR = MEDIA_ROOT / "generated"


def ensure_media_dirs() -> None:
    for directory in (MEDIA_ROOT, UPLOADS_DIR, GENERATED_DIR):
        directory.mkdir(parents=True, exist_ok=True)


def save_upload_bytes(content: bytes, extension: str, *, folder: str = "uploads") -> str:
    ensure_media_dirs()
    safe_extension = extension.lower().lstrip(".") or "bin"
    target_dir = GENERATED_DIR if folder == "generated" else UPLOADS_DIR
    filename = f"{uuid.uuid4()}.{safe_extension}"
    target_path = target_dir / filename
    target_path.write_bytes(content)
    return f"/media/{folder}/{filename}"


def save_base64_image(base64_payload: str, *, extension: str = "png") -> str:
    binary = base64.b64decode(base64_payload)
    return save_upload_bytes(binary, extension, folder="generated")


def resolve_media_path(media_url: str | None) -> str | None:
    if not media_url:
        return None
    if media_url.startswith(("http://", "https://")):
        return media_url
    if media_url.startswith("/media/"):
        return media_url
    normalized = media_url.replace("\\", "/").lstrip("/")
    if normalized.startswith("media/"):
        return f"/{normalized}"
    return f"/media/{os.path.basename(normalized)}"
