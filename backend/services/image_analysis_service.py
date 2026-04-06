from __future__ import annotations

import base64
import os
from functools import lru_cache
from urllib.parse import urlparse

import httpx

from backend import image_utils
from backend.services.media_store import save_upload_bytes
from backend.services.provider_types import (
    ImageAnalysisResult,
    ProviderConfigurationError,
    ProviderRequestError,
    VisionProvider,
)

DEFAULT_VISION_PROVIDER = (
    os.getenv("VISION_PROVIDER_NAME")
    or ("huggingface" if (os.getenv("VISION_API_KEY") or os.getenv("VISION_PROVIDER_API_KEY")) else "huggingface")
).strip().lower()
VISION_TIMEOUT_SECONDS = float(os.getenv("VISION_PROVIDER_TIMEOUT_SECONDS", "120"))
VISION_API_KEY = os.getenv("VISION_API_KEY") or os.getenv("VISION_PROVIDER_API_KEY")
VISION_BASE_URL = os.getenv("VISION_PROVIDER_BASE_URL", "https://router.huggingface.co/v1")
DEFAULT_HF_VISION_MODEL = os.getenv("VISION_PROVIDER_MODEL", "Qwen/Qwen2.5-VL-7B-Instruct")


def _guess_filename(image_url: str, content_type: str | None = None) -> str:
    path = urlparse(image_url).path
    name = path.rsplit("/", 1)[-1] or "image"
    if "." in name:
        return name
    if (content_type or "").lower() == "image/png":
        return f"{name}.png"
    return f"{name}.jpg"


def _question_or_default(question: str | None) -> str:
    normalized = (question or "").strip()
    return normalized or "Describe this image clearly and concisely."


def _download_image(image_url: str) -> tuple[bytes, str | None, str]:
    try:
        with httpx.Client(timeout=VISION_TIMEOUT_SECONDS, follow_redirects=True) as client:
            response = client.get(image_url)
            response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise ProviderRequestError(f"Could not fetch the image URL: {exc.response.status_code}.") from exc
    except httpx.HTTPError as exc:
        raise ProviderRequestError("Could not download the image URL.") from exc

    content = response.content
    content_type = response.headers.get("content-type", "").split(";")[0].strip().lower() or None
    filename = _guess_filename(image_url, content_type)
    return content, content_type, filename


def _prepare_local_image(
    *,
    image_bytes: bytes,
    filename: str,
    content_type: str | None,
) -> tuple[image_utils.PreparedImage, str]:
    try:
        extension = image_utils.validate_image_upload(filename, content_type, image_bytes)
        prepared = image_utils.prepare_image(image_bytes, filename, extension)
    except ValueError as exc:
        raise ProviderRequestError(str(exc)) from exc

    attachment_url = save_upload_bytes(prepared.content, prepared.extension, folder="uploads")
    return prepared, attachment_url


class OpenAICompatibleVisionProvider(VisionProvider):
    provider_name = "openai_compatible"

    def __init__(self) -> None:
        self.api_key = VISION_API_KEY
        self.base_url = VISION_BASE_URL.rstrip("/")
        self.model = DEFAULT_HF_VISION_MODEL
        if not self.api_key:
            raise ProviderConfigurationError(
                "VISION_API_KEY is required for the vision provider."
            )

    def analyze_image(
        self,
        *,
        question: str,
        image_bytes: bytes | None = None,
        image_url: str | None = None,
        filename: str | None = None,
        content_type: str | None = None,
    ) -> ImageAnalysisResult:
        if image_url and image_bytes is None:
            image_bytes, content_type, filename = _download_image(image_url)

        if image_bytes is None:
            raise ProviderRequestError("An image upload or image URL is required.")

        prepared, attachment_url = _prepare_local_image(
            image_bytes=image_bytes,
            filename=filename or "image.jpg",
            content_type=content_type,
        )

        encoded = base64.b64encode(prepared.content).decode("utf-8")
        data_url = f"data:{prepared.media_type};base64,{encoded}"
        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": _question_or_default(question)},
                        {"type": "image_url", "image_url": {"url": data_url}},
                    ],
                }
            ],
            "temperature": 0.2,
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        try:
            with httpx.Client(timeout=VISION_TIMEOUT_SECONDS) as client:
                response = client.post(f"{self.base_url}/chat/completions", json=payload, headers=headers)
                response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            detail = exc.response.text.strip() or exc.response.reason_phrase
            if exc.response.status_code == 429:
                raise ProviderRequestError("The vision provider is rate limited right now. Please try again shortly.") from exc
            raise ProviderRequestError(f"Vision provider request failed: {detail}") from exc
        except httpx.HTTPError as exc:
            raise ProviderRequestError("Could not reach the vision provider.") from exc

        data = response.json()
        analysis = (((data.get("choices") or [{}])[0]).get("message") or {}).get("content", "").strip()
        if not analysis:
            raise ProviderRequestError("The vision provider returned an empty response.")

        return ImageAnalysisResult(
            analysis=analysis,
            provider=self.provider_name,
            model=self.model,
            attachment_url=attachment_url,
            structured_notes={
                "mode": "vision",
                "width": prepared.width,
                "height": prepared.height,
                "content_type": prepared.media_type,
            },
            metadata={
                "mode": "vision",
                "width": prepared.width,
                "height": prepared.height,
                "content_type": prepared.media_type,
            },
        )


class HuggingFaceVisionProvider(OpenAICompatibleVisionProvider):
    provider_name = "huggingface"


@lru_cache(maxsize=4)
def get_vision_provider(provider_name: str | None = None) -> VisionProvider:
    normalized = (provider_name or DEFAULT_VISION_PROVIDER or "huggingface").strip().lower()
    if normalized in {"huggingface", "hf"}:
        return HuggingFaceVisionProvider()
    if normalized in {"openai_compatible", "openrouter", "openai"}:
        return OpenAICompatibleVisionProvider()
    raise ProviderConfigurationError(
        f"Unsupported vision provider '{normalized}'. Supported providers: huggingface, openai_compatible."
    )


def analyze_image(
    *,
    question: str,
    image_bytes: bytes | None = None,
    image_url: str | None = None,
    filename: str | None = None,
    content_type: str | None = None,
) -> ImageAnalysisResult:
    provider = get_vision_provider()
    return provider.analyze_image(
        question=question,
        image_bytes=image_bytes,
        image_url=image_url,
        filename=filename,
        content_type=content_type,
    )
