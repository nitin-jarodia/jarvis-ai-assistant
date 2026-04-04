"""
OCR utilities for Jarvis AI Assistant.

Uses pytesseract to extract readable text from uploaded images.
"""

from __future__ import annotations

import logging
import os

import pytesseract
from PIL import Image, ImageFilter, ImageOps

logger = logging.getLogger(__name__)

MIN_DOCUMENT_TEXT_LENGTH = 30


def configure_tesseract() -> None:
    """Configure pytesseract using an optional environment override."""
    tesseract_cmd = os.getenv("TESSERACT_CMD")
    if tesseract_cmd:
        pytesseract.pytesseract.tesseract_cmd = tesseract_cmd


def extract_text(image: Image.Image) -> str:
    """Extract OCR text from an image after lightweight preprocessing."""
    configure_tesseract()
    processed = preprocess_for_ocr(image)
    try:
        text = pytesseract.image_to_string(processed)
    except pytesseract.TesseractNotFoundError as exc:
        raise RuntimeError(
            "Tesseract OCR is not installed or not configured. Set TESSERACT_CMD if needed."
        ) from exc
    except Exception as exc:
        raise RuntimeError(f"OCR failed: {exc}") from exc

    normalized = normalize_ocr_text(text)
    logger.info("OCR extracted %d characters", len(normalized))
    return normalized


def preprocess_for_ocr(image: Image.Image) -> Image.Image:
    """Apply a small preprocessing pipeline to improve OCR quality."""
    grayscale = ImageOps.grayscale(image)
    sharpened = grayscale.filter(ImageFilter.SHARPEN)
    contrasted = ImageOps.autocontrast(sharpened)
    return contrasted


def normalize_ocr_text(text: str) -> str:
    """Normalize OCR output into compact paragraph text."""
    lines = [line.strip() for line in text.splitlines()]
    filtered_lines = [line for line in lines if line]
    return "\n".join(filtered_lines).strip()


def looks_like_document_text(text: str) -> bool:
    """Decide whether OCR output is substantial enough for text-only reasoning."""
    return len(text) > MIN_DOCUMENT_TEXT_LENGTH
