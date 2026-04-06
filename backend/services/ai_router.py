from __future__ import annotations

import re

from backend.services.provider_types import (
    ROUTE_MODE_ANALYZE_IMAGE,
    ROUTE_MODE_AUTO,
    ROUTE_MODE_CHAT,
    ROUTE_MODE_GENERATE_IMAGE,
    RouterDecision,
)

IMAGE_GENERATION_PATTERNS = (
    r"\bgenerate (an?|the)?\s*image\b",
    r"\bcreate (an?|the)?\s*(image|poster|logo|wallpaper|illustration|banner)\b",
    r"\bdraw\b",
    r"\bmake (an?|the)?\s*(poster|logo|wallpaper|image|illustration)\b",
    r"\bdesign (an?|the)?\s*(poster|logo|cover|wallpaper)\b",
    r"\bturn this into (an?|the)?\s*image\b",
)


def normalize_mode(raw_mode: str | None) -> str:
    normalized = (raw_mode or ROUTE_MODE_AUTO).strip().lower()
    if normalized in {ROUTE_MODE_AUTO, ROUTE_MODE_CHAT, ROUTE_MODE_GENERATE_IMAGE, ROUTE_MODE_ANALYZE_IMAGE}:
        return normalized
    return ROUTE_MODE_AUTO


def looks_like_image_generation_request(text: str | None) -> bool:
    normalized = (text or "").strip().lower()
    if not normalized:
        return False
    return any(re.search(pattern, normalized) for pattern in IMAGE_GENERATION_PATTERNS)


def decide_route(
    *,
    mode: str | None,
    text: str | None,
    has_image_attachment: bool = False,
) -> RouterDecision:
    normalized_mode = normalize_mode(mode)
    if normalized_mode != ROUTE_MODE_AUTO:
        return RouterDecision(mode=normalized_mode, reason="manual selection")
    if has_image_attachment:
        return RouterDecision(mode=ROUTE_MODE_ANALYZE_IMAGE, reason="image attachment present")
    if looks_like_image_generation_request(text):
        return RouterDecision(mode=ROUTE_MODE_GENERATE_IMAGE, reason="generation keywords detected")
    return RouterDecision(mode=ROUTE_MODE_CHAT, reason="default text chat")
