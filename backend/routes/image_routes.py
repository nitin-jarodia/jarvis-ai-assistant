"""
Image analysis routes for Jarvis AI Assistant.
"""

from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status

from backend import image_utils, llm_service, ocr_utils

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Images"])


@router.post("/analyze-image")
async def analyze_image(
    image: UploadFile = File(...),
    question: str = Form(...),
):
    """Analyze an uploaded image using OCR-first routing with Ollama fallback."""
    user_question = question.strip()
    if not user_question:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Question is required.",
        )

    original_name = image.filename or "image"
    content = await image.read()

    try:
        extension = image_utils.validate_image_upload(
            original_name,
            image.content_type,
            content,
        )
        prepared_image = await asyncio.to_thread(
            image_utils.prepare_image,
            content,
            original_name,
            extension,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=_image_error_status(str(exc)),
            detail=str(exc),
        ) from exc

    try:
        extracted_text = await asyncio.to_thread(
            ocr_utils.extract_text,
            prepared_image.image,
        )
        if ocr_utils.looks_like_document_text(extracted_text):
            logger.info("Image '%s' routed through OCR text flow", original_name)
            answer = await asyncio.to_thread(
                llm_service.answer_with_text_context,
                user_question,
                extracted_text,
            )
            return {
                "answer": answer,
                "mode": "ocr-text",
                "extracted_text_length": len(extracted_text),
            }

        logger.info("Image '%s' routed through vision flow", original_name)
        answer = await asyncio.to_thread(
            llm_service.answer_with_vision,
            user_question,
            prepared_image.content,
        )
        return {
            "answer": answer,
            "mode": "vision",
            "extracted_text_length": len(extracted_text),
        }
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc


def _image_error_status(detail: str) -> int:
    detail_lower = detail.lower()
    if "too large" in detail_lower:
        return status.HTTP_413_REQUEST_ENTITY_TOO_LARGE
    if "unsupported image type" in detail_lower:
        return status.HTTP_400_BAD_REQUEST
    return status.HTTP_422_UNPROCESSABLE_ENTITY
