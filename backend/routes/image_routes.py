"""Image generation and analysis routes for Jarvis AI Assistant."""

from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status

from backend import schemas
from backend.dependencies import get_current_user
from backend.services import image_generation
from backend.services import image_analysis_service as image_analysis
from backend.services.provider_types import ProviderConfigurationError, ProviderRequestError

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Images"])


def _provider_error_status(detail: str) -> int:
    detail_lower = detail.lower()
    if "too large" in detail_lower:
        return status.HTTP_413_REQUEST_ENTITY_TOO_LARGE
    if "unsupported" in detail_lower or "required" in detail_lower:
        return status.HTTP_400_BAD_REQUEST
    if "rate limited" in detail_lower:
        return status.HTTP_429_TOO_MANY_REQUESTS
    if "configured" in detail_lower or "api key" in detail_lower:
        return status.HTTP_503_SERVICE_UNAVAILABLE
    return status.HTTP_422_UNPROCESSABLE_ENTITY


async def _run_image_analysis(
    *,
    image: UploadFile | None,
    image_url: str | None,
    question: str | None,
) -> schemas.ImageAnalysisResponse:
    content = await image.read() if image else None
    try:
        result = await asyncio.to_thread(
            image_analysis.analyze_image,
            question=(question or "").strip(),
            image_bytes=content,
            image_url=(image_url or "").strip() or None,
            filename=image.filename if image else None,
            content_type=image.content_type if image else None,
        )
    except (ProviderRequestError, ProviderConfigurationError) as exc:
        raise HTTPException(status_code=_provider_error_status(str(exc)), detail=str(exc)) from exc

    return schemas.ImageAnalysisResponse(
        analysis=result.analysis,
        attachment_url=result.attachment_url,
        provider=result.provider,
        model=result.model,
        metadata=result.metadata,
        structured_notes=result.structured_notes,
    )


@router.post("/api/image/generate", response_model=schemas.ImageGenerationResponse)
async def generate_image(
    payload: schemas.ImageGenerationRequest,
    current_user_id: int = Depends(get_current_user),
):
    del current_user_id
    try:
        result = await asyncio.to_thread(
            image_generation.generate_image,
            prompt=payload.prompt,
            style=payload.style,
            aspect_ratio=payload.aspect_ratio,
            size=payload.size,
        )
    except (ProviderRequestError, ProviderConfigurationError) as exc:
        raise HTTPException(status_code=_provider_error_status(str(exc)), detail=str(exc)) from exc

    return schemas.ImageGenerationResponse(
        prompt=result.prompt,
        image_url=result.image_url,
        provider=result.provider,
        model=result.model,
        metadata=result.metadata,
    )


@router.post("/api/image/analyze", response_model=schemas.ImageAnalysisResponse)
async def analyze_image_api(
    image: UploadFile | None = File(default=None),
    image_url: str | None = Form(default=None),
    question: str | None = Form(default=None),
    current_user_id: int = Depends(get_current_user),
):
    del current_user_id
    if image is None and not (image_url or "").strip():
        raise HTTPException(status_code=400, detail="Provide either an uploaded image or an image URL.")
    return await _run_image_analysis(image=image, image_url=image_url, question=question)


@router.post("/analyze-image")
async def analyze_image_legacy(
    image: UploadFile | None = File(default=None),
    image_url: str | None = Form(default=None),
    question: str | None = Form(default=None),
):
    if image is None and not (image_url or "").strip():
        raise HTTPException(status_code=400, detail="Provide either an uploaded image or an image URL.")
    return await _run_image_analysis(image=image, image_url=image_url, question=question)
