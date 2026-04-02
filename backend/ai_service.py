"""
AI service module for Jarvis AI Assistant.

Communicates with the Groq API for chat completions.
Model: llama-3.3-70b-versatile
"""

import os
import time
import logging
from pathlib import Path

from groq import Groq, APIStatusError
from dotenv import load_dotenv

# Explicitly load .env from the project root (robust against different CWDs)
_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(dotenv_path=_ROOT / ".env")

logger = logging.getLogger(__name__)

# ─── Configuration ────────────────────────────────────────────────────────────

MODEL_NAME = "llama-3.3-70b-versatile"

SYSTEM_PROMPT = """You are Jarvis, an intelligent AI assistant.
You remember previous conversation context.
Give accurate, structured, and helpful responses.
Use proper formatting, bullet points, and emojis where appropriate.
Make answers clean, readable, and visually appealing.
For coding: use proper indentation and code blocks with language identifiers.
For math: show steps clearly.
Do not give messy or unformatted output."""

# ─── Groq Client (module-level singleton) ─────────────────────────────────────

def _build_client() -> Groq | None:
    """Build and return a Groq client, or None if the key is missing."""
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        return None
    return Groq(api_key=api_key)

_client: Groq | None = _build_client()

# ─── Health Check ─────────────────────────────────────────────────────────────

def check_ai_service() -> dict:
    """Check if the AI service is configured properly."""
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        logger.warning("GROQ_API_KEY is not set.")
        return {
            "status": "error",
            "model": MODEL_NAME,
            "detail": "GROQ_API_KEY is not set in the environment.",
        }
    logger.info("GROQ_API_KEY is loaded successfully.")
    return {
        "status": "ok",
        "model": MODEL_NAME,
        "detail": "Configured successfully.",
    }

# ─── Chat ─────────────────────────────────────────────────────────────────────

def generate_response(
    message: str,
    history: list | None = None,
    system_prompt_override: str | None = None,
) -> str:
    """
    Send a message to the Groq API and return the assistant's reply.
    Includes conversation history for context-aware responses.
    """
    global _client

    # Reload client if it wasn't available at startup
    if _client is None:
        _client = _build_client()

    if _client is None:
        logger.error("Cannot call Groq API: GROQ_API_KEY is missing.")
        return "⚠️ Jarvis is not configured. Please set the GROQ_API_KEY in your .env file."

    active_system_prompt = system_prompt_override or SYSTEM_PROMPT
    messages = [{"role": "system", "content": active_system_prompt}]
    if history:
        messages.extend(history)
    messages.append({"role": "user", "content": message})

    start_time = time.time()

    try:
        response = _client.chat.completions.create(
            model=MODEL_NAME,
            messages=messages,
            temperature=0.5,
            max_tokens=2048,
        )

        reply = response.choices[0].message.content.strip()
        elapsed = time.time() - start_time
        logger.info(
            "Groq response | model=%s | tokens=%s | time=%.2fs",
            MODEL_NAME,
            getattr(response.usage, "total_tokens", "?"),
            elapsed,
        )
        return reply

    except APIStatusError as e:
        elapsed = time.time() - start_time
        status_code = e.status_code

        if status_code == 401:
            logger.error("Groq authentication failed (401). Check your GROQ_API_KEY.")
            return "⚠️ Authentication failed. Please check your GROQ_API_KEY."

        if status_code == 429:
            logger.warning("Groq rate limit hit (429). Retry after a moment.")
            return "⚠️ I'm receiving too many requests right now. Please wait a moment and try again."

        if status_code in (502, 503, 504):
            logger.error("Groq server error (%d). Elapsed: %.2fs", status_code, elapsed)
            return "⚠️ The AI service is temporarily unavailable. Please try again shortly."

        logger.error("Groq API error %d: %s", status_code, e.message)
        return f"⚠️ An API error occurred (code {status_code}). Please try again."

    except Exception as e:
        elapsed = time.time() - start_time
        logger.error("Unexpected error during Groq call (%.2fs): %s", elapsed, e)
        return "⚠️ An unexpected error occurred. Please try again."
