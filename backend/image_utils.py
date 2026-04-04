"""
Image utilities for Jarvis AI Assistant.

Handles image validation, loading, normalization, and resizing for OCR/vision.
"""

from __future__ import annotations

import io
import logging
from dataclasses import dataclass

from PIL import Image, ImageOps

logger = logging.getLogger(__name__)

MAX_IMAGE_BYTES = 8 * 1024 * 1024
ALLOWED_IMAGE_EXTENSIONS = {"jpg", "jpeg", "png"}
ALLOWED_IMAGE_CONTENT_TYPES = {
    "image/jpeg",
    "image/jpg",
    "image/png",
    "application/octet-stream",
}
MAX_IMAGE_DIMENSION = 1600


@dataclass
class PreparedImage:
    filename: str
    extension: str
    media_type: str
    image: Image.Image
    content: bytes
    width: int
    height: int


def validate_image_upload(filename: str, content_type: str | None, content: bytes) -> str:
    """Validate an uploaded image and return the normalized extension."""
    if not filename:
        raise ValueError("A file name is required.")

    extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if extension not in ALLOWED_IMAGE_EXTENSIONS:
        raise ValueError("Unsupported image type. Only JPG and PNG files are allowed.")

    if not content:
        raise ValueError("Uploaded image is empty.")

    if len(content) > MAX_IMAGE_BYTES:
        raise ValueError("Image too large. Maximum size is 8 MB.")

    normalized_content_type = (content_type or "").split(";")[0].strip().lower()
    if normalized_content_type and normalized_content_type not in ALLOWED_IMAGE_CONTENT_TYPES:
        logger.warning(
            "Image content-type mismatch for %s: %s",
            filename,
            normalized_content_type,
        )

    return extension


def prepare_image(content: bytes, filename: str, extension: str) -> PreparedImage:
    """Load, normalize, and resize an image for downstream OCR/vision tasks."""
    try:
        with Image.open(io.BytesIO(content)) as source_image:
            normalized = ImageOps.exif_transpose(source_image).convert("RGB")
    except Exception as exc:
        raise ValueError(f"Failed to open image: {exc}") from exc

    resized = normalized.copy()
    resized.thumbnail((MAX_IMAGE_DIMENSION, MAX_IMAGE_DIMENSION))

    output = io.BytesIO()
    save_format = "PNG" if extension == "png" else "JPEG"
    save_kwargs = {"optimize": True}
    if save_format == "JPEG":
        save_kwargs["quality"] = 90

    resized.save(output, format=save_format, **save_kwargs)
    prepared_content = output.getvalue()
    media_type = "image/png" if save_format == "PNG" else "image/jpeg"

    logger.info(
        "Prepared image '%s' | %dx%d -> %dx%d | %d bytes",
        filename,
        normalized.width,
        normalized.height,
        resized.width,
        resized.height,
        len(prepared_content),
    )

    return PreparedImage(
        filename=filename,
        extension=extension,
        media_type=media_type,
        image=resized,
        content=prepared_content,
        width=resized.width,
        height=resized.height,
    )
