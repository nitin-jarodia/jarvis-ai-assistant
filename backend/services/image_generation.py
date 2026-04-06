from __future__ import annotations

import logging
import os
from functools import lru_cache
from urllib.parse import quote

import httpx

from backend.services.media_store import save_base64_image
from backend.services.provider_types import (
    ImageGenerationProvider,
    ImageGenerationResult,
    ProviderConfigurationError,
    ProviderRequestError,
)

logger = logging.getLogger(__name__)

DEFAULT_IMAGE_PROVIDER = os.getenv("IMAGE_PROVIDER_NAME", "pollinations").strip().lower()
DEFAULT_IMAGE_MODEL = os.getenv("IMAGE_PROVIDER_MODEL", "flux")
OPENAI_IMAGE_BASE_URL = os.getenv("IMAGE_PROVIDER_BASE_URL", "https://api.openai.com/v1")
IMAGE_API_KEY = os.getenv("IMAGE_API_KEY") or os.getenv("IMAGE_PROVIDER_API_KEY")
IMAGE_TIMEOUT_SECONDS = float(os.getenv("IMAGE_PROVIDER_TIMEOUT_SECONDS", "90"))

_ASPECT_RATIO_MAP = {
    "1:1": (1024, 1024),
    "4:3": (1152, 864),
    "3:4": (864, 1152),
    "16:9": (1344, 768),
    "9:16": (768, 1344),
}
_SIZE_MAP = {
    "sm": (768, 768),
    "md": (1024, 1024),
    "lg": (1344, 1024),
}


def _resolve_dimensions(aspect_ratio: str | None, size: str | None) -> tuple[int, int]:
    normalized_aspect = (aspect_ratio or "").strip().lower()
    normalized_size = (size or "").strip().lower()

    if normalized_size in _SIZE_MAP:
        return _SIZE_MAP[normalized_size]
    if normalized_aspect in _ASPECT_RATIO_MAP:
        return _ASPECT_RATIO_MAP[normalized_aspect]
    return 1024, 1024


class PollinationsImageGenerationProvider(ImageGenerationProvider):
    provider_name = "pollinations"

    def __init__(self, model: str | None = None) -> None:
        self.model = model or DEFAULT_IMAGE_MODEL or "flux"

    def generate_image(
        self,
        *,
        prompt: str,
        style: str | None = None,
        aspect_ratio: str | None = None,
        size: str | None = None,
    ) -> ImageGenerationResult:
        width, height = _resolve_dimensions(aspect_ratio, size)
        prompt_parts = [prompt.strip()]
        if style:
            prompt_parts.append(f"Style: {style.strip()}")
        composed_prompt = ", ".join(part for part in prompt_parts if part)
        if not composed_prompt:
            raise ProviderRequestError("An image prompt is required.")

        url = (
            f"https://image.pollinations.ai/prompt/{quote(composed_prompt)}"
            f"?width={width}&height={height}&model={quote(self.model)}&nologo=true"
        )
        logger.info("Image generation routed to Pollinations | model=%s", self.model)
        return ImageGenerationResult(
            prompt=prompt,
            image_url=url,
            provider=self.provider_name,
            model=self.model,
            metadata={
                "style": style,
                "aspect_ratio": aspect_ratio or "1:1",
                "size": size or "md",
                "width": width,
                "height": height,
            },
        )


class OpenAIImageGenerationProvider(ImageGenerationProvider):
    provider_name = "openai"

    def __init__(self) -> None:
        self.api_key = IMAGE_API_KEY
        self.model = os.getenv("IMAGE_PROVIDER_MODEL", "gpt-image-1")
        self.base_url = OPENAI_IMAGE_BASE_URL.rstrip("/")
        if not self.api_key:
            raise ProviderConfigurationError("IMAGE_API_KEY is required for the OpenAI image provider.")

    def generate_image(
        self,
        *,
        prompt: str,
        style: str | None = None,
        aspect_ratio: str | None = None,
        size: str | None = None,
    ) -> ImageGenerationResult:
        if not prompt.strip():
            raise ProviderRequestError("An image prompt is required.")

        dimensions = _resolve_dimensions(aspect_ratio, size)
        request_size = f"{dimensions[0]}x{dimensions[1]}"
        prompt_text = prompt.strip()
        if style:
            prompt_text = f"{prompt_text}\n\nStyle guidance: {style.strip()}"

        payload = {
            "model": self.model,
            "prompt": prompt_text,
            "size": request_size,
            "response_format": "b64_json",
        }
        headers = {"Authorization": f"Bearer {self.api_key}"}

        try:
            with httpx.Client(timeout=IMAGE_TIMEOUT_SECONDS) as client:
                response = client.post(f"{self.base_url}/images/generations", json=payload, headers=headers)
                response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            detail = exc.response.text.strip() or exc.response.reason_phrase
            if exc.response.status_code == 429:
                raise ProviderRequestError("The image provider is rate limited right now. Please try again shortly.") from exc
            raise ProviderRequestError(f"Image provider request failed: {detail}") from exc
        except httpx.HTTPError as exc:
            raise ProviderRequestError("Could not reach the image generation provider.") from exc

        data = response.json()
        item = (data.get("data") or [{}])[0]
        image_url = item.get("url")
        if not image_url and item.get("b64_json"):
            image_url = save_base64_image(item["b64_json"])
        if not image_url:
            raise ProviderRequestError("The image provider returned an empty result.")

        logger.info("Image generation routed to OpenAI-compatible endpoint | model=%s", self.model)
        return ImageGenerationResult(
            prompt=prompt,
            image_url=image_url,
            provider=self.provider_name,
            model=self.model,
            metadata={
                "style": style,
                "aspect_ratio": aspect_ratio or "1:1",
                "size": request_size,
            },
        )


@lru_cache(maxsize=4)
def get_image_generation_provider(provider_name: str | None = None) -> ImageGenerationProvider:
    normalized = (provider_name or DEFAULT_IMAGE_PROVIDER or "pollinations").strip().lower()
    if normalized == "pollinations":
        return PollinationsImageGenerationProvider()
    if normalized in {"openai", "openai-compatible"}:
        return OpenAIImageGenerationProvider()
    raise ProviderConfigurationError(
        f"Unsupported image provider '{normalized}'. Supported providers: pollinations, openai."
    )


def generate_image(
    *,
    prompt: str,
    style: str | None = None,
    aspect_ratio: str | None = None,
    size: str | None = None,
) -> ImageGenerationResult:
    provider = get_image_generation_provider()
    return provider.generate_image(
        prompt=prompt,
        style=style,
        aspect_ratio=aspect_ratio,
        size=size,
    )
