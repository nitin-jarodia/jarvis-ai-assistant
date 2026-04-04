"""
Ollama-backed LLM service for image understanding.

Uses local Ollama models for both OCR-grounded text answers and vision analysis.
"""

from __future__ import annotations

import base64
import logging
import os

import httpx

logger = logging.getLogger(__name__)

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
OLLAMA_TEXT_MODEL = os.getenv("OLLAMA_TEXT_MODEL", "llama3")
OLLAMA_VISION_MODEL = os.getenv("OLLAMA_VISION_MODEL", "llava")
OLLAMA_TIMEOUT_SECONDS = 120.0


def answer_with_text_context(question: str, extracted_text: str) -> str:
    """Answer a question using OCR text as the only context."""
    prompt = (
        "You are Jarvis.\n"
        "Use only the provided OCR text to answer the question.\n"
        "If the answer is unclear from the OCR text, say so briefly.\n\n"
        f"Context:\n{extracted_text}\n\n"
        f"Question: {question}\n"
        "Answer clearly and concisely."
    )
    return _generate(model=OLLAMA_TEXT_MODEL, prompt=prompt)


def answer_with_vision(question: str, image_bytes: bytes) -> str:
    """Answer a question about an image using a vision-capable Ollama model."""
    prompt = (
        "You are Jarvis.\n"
        "Analyze the image and answer the question clearly and concisely.\n\n"
        f"Question: {question}\n"
        "Answer clearly and concisely."
    )
    encoded_image = base64.b64encode(image_bytes).decode("utf-8")
    return _generate(model=OLLAMA_VISION_MODEL, prompt=prompt, images=[encoded_image])


def _generate(model: str, prompt: str, images: list[str] | None = None) -> str:
    """Call Ollama's generate endpoint and return the response text."""
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
    }
    if images:
        payload["images"] = images

    try:
        with httpx.Client(timeout=OLLAMA_TIMEOUT_SECONDS) as client:
            response = client.post(f"{OLLAMA_BASE_URL}/api/generate", json=payload)
            response.raise_for_status()
    except httpx.ConnectError as exc:
        logger.error("Failed to connect to Ollama at %s", OLLAMA_BASE_URL)
        raise RuntimeError("Could not connect to Ollama. Make sure Ollama is running.") from exc
    except httpx.HTTPStatusError as exc:
        detail = exc.response.text.strip() or exc.response.reason_phrase
        logger.error("Ollama request failed: %s", detail)
        raise RuntimeError(f"Ollama request failed: {detail}") from exc
    except httpx.HTTPError as exc:
        logger.error("Unexpected Ollama HTTP error: %s", exc)
        raise RuntimeError("Failed to communicate with Ollama.") from exc

    data = response.json()
    answer = (data.get("response") or "").strip()
    if not answer:
        raise RuntimeError("Ollama returned an empty response.")

    logger.info("Ollama response generated with model '%s'", model)
    return answer
