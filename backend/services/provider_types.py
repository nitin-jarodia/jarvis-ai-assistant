from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


MESSAGE_TYPE_TEXT = "text"
MESSAGE_TYPE_IMAGE_GENERATION = "image_generation"
MESSAGE_TYPE_IMAGE_ANALYSIS = "image_analysis"
SUPPORTED_MESSAGE_TYPES = (
    MESSAGE_TYPE_TEXT,
    MESSAGE_TYPE_IMAGE_GENERATION,
    MESSAGE_TYPE_IMAGE_ANALYSIS,
)

ROUTE_MODE_AUTO = "auto"
ROUTE_MODE_CHAT = "chat"
ROUTE_MODE_GENERATE_IMAGE = "generate_image"
ROUTE_MODE_ANALYZE_IMAGE = "analyze_image"
SUPPORTED_ROUTE_MODES = (
    ROUTE_MODE_AUTO,
    ROUTE_MODE_CHAT,
    ROUTE_MODE_GENERATE_IMAGE,
    ROUTE_MODE_ANALYZE_IMAGE,
)


class ProviderConfigurationError(RuntimeError):
    """Raised when a provider is selected but not configured correctly."""


class ProviderRequestError(RuntimeError):
    """Raised when a provider call fails in a user-visible way."""


@dataclass(slots=True)
class ImageGenerationResult:
    prompt: str
    image_url: str | None
    provider: str
    model: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ImageAnalysisResult:
    analysis: str
    provider: str
    model: str | None = None
    attachment_url: str | None = None
    structured_notes: dict[str, Any] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class RouterDecision:
    mode: str
    reason: str


class ImageGenerationProvider(Protocol):
    provider_name: str

    def generate_image(
        self,
        *,
        prompt: str,
        style: str | None = None,
        aspect_ratio: str | None = None,
        size: str | None = None,
    ) -> ImageGenerationResult:
        ...


class VisionProvider(Protocol):
    provider_name: str

    def analyze_image(
        self,
        *,
        question: str,
        image_bytes: bytes | None = None,
        image_url: str | None = None,
        filename: str | None = None,
        content_type: str | None = None,
    ) -> ImageAnalysisResult:
        ...
