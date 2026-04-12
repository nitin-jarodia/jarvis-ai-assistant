"""
AI service module for Jarvis AI Assistant.

Communicates with the Groq API for chat completions.
Model: llama-3.3-70b-versatile
"""

import logging
import os
import re
import time
from collections.abc import Iterator
from threading import Event
from typing import Any
import json
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from groq import APIConnectionError, APIStatusError, APITimeoutError, Groq

# Explicitly load .env from the project root (robust against different CWDs)
_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(dotenv_path=_ROOT / ".env")

logger = logging.getLogger(__name__)

# ─── Configuration ────────────────────────────────────────────────────────────

MODEL_NAME = "llama-3.3-70b-versatile"
GROQ_TIMEOUT_SECONDS = float(os.getenv("GROQ_TIMEOUT_SECONDS", "45"))

SYSTEM_PROMPT = """You are Jarvis, an intelligent AI assistant.
You remember previous conversation context.
Give accurate, structured, and helpful responses.
Use clean formatting.
For coding: use proper indentation and code blocks with language identifiers.
For math: show steps clearly.
Do not give messy or unformatted output."""

CLASSIFIER_PROMPT_TEMPLATE = """Classify this query into one word:
coding, research, planning, debugging.

Query: {input}
Answer:"""

AGENT_SYSTEM_PROMPTS = {
    "coding": "You are Jarvis Coding. Give concise, practical coding help. Use code blocks only when useful.",
    "research": "You are Jarvis Research. Give concise, accurate explanations with only relevant detail.",
    "planning": "You are Jarvis Planner. Provide short actionable plans with prioritized next steps.",
    "debugging": "You are Jarvis Debug. Identify likely causes, quick checks, and concrete fixes.",
}

VALID_AGENT_TYPES = tuple(AGENT_SYSTEM_PROMPTS.keys())
VALID_SELECTED_AGENT_TYPES = ("auto", *VALID_AGENT_TYPES)

# ─── Groq Client (module-level singleton) ─────────────────────────────────────

def _build_client() -> Groq | None:
    """Build and return a Groq client, or None if the key is missing."""
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        return None
    return Groq(api_key=api_key, timeout=GROQ_TIMEOUT_SECONDS, max_retries=1)

_client: Groq | None = None

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
    return {
        "status": "ok",
        "model": MODEL_NAME,
        "detail": f"Configured successfully. Timeout: {GROQ_TIMEOUT_SECONDS}s.",
    }

# ─── Chat ─────────────────────────────────────────────────────────────────────

def _ensure_client() -> Groq | None:
    global _client

    if _client is None:
        _client = _build_client()
    return _client


def _coerce_message_content(content: Any) -> str:
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        text_parts: list[str] = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                text_parts.append(str(item.get("text", "")))
        return " ".join(part.strip() for part in text_parts if part).strip()
    return str(content or "").strip()


def generate_response_from_messages(
    messages: list[dict[str, Any]],
    failure_message: str | None = None,
    *,
    max_tokens: int = 2048,
    temperature: float = 0.5,
) -> str:
    """Send a prepared message list to Groq and return the assistant reply."""
    client = _ensure_client()
    if client is None:
        logger.error("Cannot call Groq API: GROQ_API_KEY is missing.")
        return failure_message or "Jarvis is not configured. Please set the GROQ_API_KEY in your .env file."

    start_time = time.time()

    try:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )

        reply = _coerce_message_content(response.choices[0].message.content)
        elapsed = time.time() - start_time
        logger.info(
            "Groq response | model=%s | tokens=%s | time=%.2fs",
            MODEL_NAME,
            getattr(response.usage, "total_tokens", "?"),
            elapsed,
        )
        if reply:
            return reply
        return failure_message or "I could not generate a response right now. Please try again."

    except APITimeoutError as exc:
        elapsed = time.time() - start_time
        logger.error("Groq request timed out after %.2fs", elapsed)
        return failure_message or "The AI request timed out. Please try again."

    except APIConnectionError as exc:
        elapsed = time.time() - start_time
        logger.error("Groq connection error after %.2fs: %s", elapsed, exc)
        return failure_message or "Could not reach the AI service. Please try again."

    except APIStatusError as e:
        elapsed = time.time() - start_time
        status_code = e.status_code

        if status_code == 401:
            logger.error("Groq authentication failed (401). Check your GROQ_API_KEY.")
            return failure_message or "Authentication failed. Please check your GROQ_API_KEY."

        if status_code == 429:
            logger.warning("Groq rate limit hit (429). Retry after a moment.")
            return failure_message or "I'm receiving too many requests right now. Please wait a moment and try again."

        if status_code in (502, 503, 504):
            logger.error("Groq server error (%d). Elapsed: %.2fs", status_code, elapsed)
            return failure_message or "The AI service is temporarily unavailable. Please try again shortly."

        logger.error("Groq API error %d: %s", status_code, e.message)
        return failure_message or f"An API error occurred (code {status_code}). Please try again."

    except Exception as e:
        elapsed = time.time() - start_time
        logger.error("Unexpected error during Groq call (%.2fs): %s", elapsed, e)
        return failure_message or "An unexpected error occurred. Please try again."


def stream_response_from_messages(
    messages: list[dict[str, Any]],
    failure_message: str | None = None,
    *,
    max_tokens: int = 2048,
    temperature: float = 0.5,
    stop_event: Event | None = None,
) -> Iterator[str]:
    """Yield streamed text deltas from Groq, falling back to a final message on failure."""
    client = _ensure_client()
    fallback = failure_message or "I could not generate a response right now. Please try again."
    if client is None:
        logger.error("Cannot call Groq API: GROQ_API_KEY is missing.")
        yield "Jarvis is not configured. Please set the GROQ_API_KEY in your .env file."
        return

    start_time = time.time()
    parts: list[str] = []

    try:
        stream = client.chat.completions.create(
            model=MODEL_NAME,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
        )

        for chunk in stream:
            if stop_event and stop_event.is_set():
                close_stream = getattr(stream, "close", None)
                if callable(close_stream):
                    try:
                        close_stream()
                    except Exception:
                        pass
                break
            delta = ""
            if getattr(chunk, "choices", None):
                delta = chunk.choices[0].delta.content or ""
            if delta:
                parts.append(delta)
                yield delta

        reply = "".join(parts).strip()
        elapsed = time.time() - start_time
        logger.info(
            "Groq streamed response | model=%s | chars=%d | time=%.2fs",
            MODEL_NAME,
            len(reply),
            elapsed,
        )
        if not reply:
            yield fallback

    except APITimeoutError:
        elapsed = time.time() - start_time
        logger.error("Groq stream timed out after %.2fs", elapsed)
        if parts:
            return
        yield "The AI request timed out. Please try again."

    except APIConnectionError as exc:
        elapsed = time.time() - start_time
        logger.error("Groq stream connection error after %.2fs: %s", elapsed, exc)
        if parts:
            return
        yield "Could not reach the AI service. Please try again."

    except APIStatusError as e:
        elapsed = time.time() - start_time
        status_code = e.status_code

        if status_code == 401:
            logger.error("Groq authentication failed during stream (401). Check your GROQ_API_KEY.")
            if not parts:
                yield "Authentication failed. Please check your GROQ_API_KEY."
            return

        if status_code == 429:
            logger.warning("Groq rate limit hit during stream (429).")
            if not parts:
                yield "I'm receiving too many requests right now. Please wait a moment and try again."
            return

        if status_code in (502, 503, 504):
            logger.error("Groq stream server error (%d). Elapsed: %.2fs", status_code, elapsed)
            if not parts:
                yield "The AI service is temporarily unavailable. Please try again shortly."
            return

        logger.error("Groq stream API error %d: %s", status_code, e.message)
        if not parts:
            yield f"An API error occurred (code {status_code}). Please try again."

    except Exception as e:
        elapsed = time.time() - start_time
        logger.error("Unexpected error during Groq stream (%.2fs): %s", elapsed, e)
        if not parts:
            yield fallback


def generateResponse(
    messages: list[dict[str, Any]],
    failure_message: str | None = None,
    *,
    max_tokens: int = 2048,
    temperature: float = 0.5,
) -> str:
    """Standard Groq chat function used across the app."""
    return generate_response_from_messages(
        messages,
        failure_message,
        max_tokens=max_tokens,
        temperature=temperature,
    )


def _normalize_agent_type(raw_value: str | None) -> str:
    cleaned = (raw_value or "").strip().lower()
    if cleaned in VALID_AGENT_TYPES:
        return cleaned

    if any(token in cleaned for token in ("debug", "error", "traceback", "exception", "bug")):
        return "debugging"
    if any(token in cleaned for token in ("plan", "roadmap", "strategy", "schedule")):
        return "planning"
    if any(token in cleaned for token in ("code", "python", "java", "cpp", "bugfix", "leetcode", "algorithm", "dsa")):
        return "coding"
    return "research"


def _normalize_selected_agent(raw_value: str | None) -> str:
    cleaned = (raw_value or "").strip().lower()
    return cleaned if cleaned in VALID_SELECTED_AGENT_TYPES else "auto"


@lru_cache(maxsize=256)
def _classify_query_cached(normalized_input: str) -> str:
    if not normalized_input:
        return "research"

    classifier_messages = [
        {
            "role": "system",
            "content": "Return one word only: coding, research, planning, or debugging.",
        },
        {
            "role": "user",
            "content": CLASSIFIER_PROMPT_TEMPLATE.format(input=normalized_input),
        },
    ]
    raw_result = generateResponse(
        classifier_messages,
        failure_message="research",
        max_tokens=4,
        temperature=0,
    )
    return _normalize_agent_type(raw_result)


def classify_query(user_input: str) -> str:
    normalized_input = re.sub(r"\s+", " ", user_input.strip().lower())
    return _classify_query_cached(normalized_input)


def build_agent_system_prompt(agent_type: str) -> str:
    return AGENT_SYSTEM_PROMPTS.get(agent_type, AGENT_SYSTEM_PROMPTS["research"])


def prepare_agent_messages(
    *,
    user_input: str,
    history: list[dict[str, Any]] | None = None,
    selected_agent: str = "auto",
) -> tuple[str, list[dict[str, str]]]:
    """Resolve the active agent and return the final Groq message list."""
    normalized_selection = _normalize_selected_agent(selected_agent)
    agent_type = (
        normalized_selection
        if normalized_selection != "auto"
        else classify_query(user_input)
    )
    messages = [{"role": "system", "content": build_agent_system_prompt(agent_type)}]
    if history:
        messages.extend(history)
    messages.append({"role": "user", "content": user_input})
    return agent_type, messages


def complete_with_tools(
    *,
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]],
    failure_message: str | None = None,
    max_tokens: int = 1024,
    temperature: float = 0.2,
) -> dict[str, Any]:
    """Run a non-streaming planning call that may return tool calls."""
    client = _ensure_client()
    if client is None:
        fallback = failure_message or "Jarvis is not configured. Please set the GROQ_API_KEY in your .env file."
        return {"content": fallback, "tool_calls": []}

    start_time = time.time()
    try:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=messages,
            tools=tools,
            tool_choice="auto",
            temperature=temperature,
            max_tokens=max_tokens,
        )
        message = response.choices[0].message
        tool_calls: list[dict[str, Any]] = []
        for call in getattr(message, "tool_calls", None) or []:
            raw_arguments = call.function.arguments or "{}"
            try:
                arguments = json.loads(raw_arguments)
                if not isinstance(arguments, dict):
                    arguments = {}
            except json.JSONDecodeError:
                arguments = {}
            tool_calls.append(
                {
                    "id": call.id,
                    "name": call.function.name,
                    "arguments": arguments,
                    "raw_arguments": raw_arguments,
                }
            )

        logger.info(
            "Groq tool planning | model=%s | tool_calls=%d | time=%.2fs",
            MODEL_NAME,
            len(tool_calls),
            time.time() - start_time,
        )
        return {
            "content": _coerce_message_content(message.content),
            "tool_calls": tool_calls,
        }
    except Exception as exc:
        logger.error("Tool planning call failed: %s", exc)
        return {
            "content": failure_message or "I couldn't complete that request right now. Please try again.",
            "tool_calls": [],
        }


def generate_agent_response(
    *,
    user_input: str,
    history: list[dict[str, str]] | None = None,
    selected_agent: str = "auto",
) -> tuple[str, str]:
    """
    Route to the selected specialist agent.
    Manual agent selection uses a single Groq call. Auto routing uses a cheap classifier first.
    """
    agent_type, messages = prepare_agent_messages(
        user_input=user_input,
        history=history,
        selected_agent=selected_agent,
    )
    reply = generateResponse(
        messages,
        failure_message="I couldn't generate a response right now. Please try again.",
    )
    return agent_type, reply


def generate_response(
    message: str,
    history: list | None = None,
    system_prompt_override: str | None = None,
) -> str:
    """
    Send a message to the Groq API and return the assistant's reply.
    Includes conversation history for context-aware responses.
    """
    active_system_prompt = system_prompt_override or SYSTEM_PROMPT
    messages = [{"role": "system", "content": active_system_prompt}]
    if history:
        messages.extend(history)
    messages.append({"role": "user", "content": message})
    return generateResponse(messages)
