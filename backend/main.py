"""
Jarvis AI Assistant — FastAPI main application.
Run with: uvicorn backend.main:app --reload
      or: python run.py
"""

import asyncio
import json
import os
import uuid
import logging
import threading
from contextlib import asynccontextmanager
from typing import List

from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Form, Request, status
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from backend.auth import router as auth_router
from backend.database import get_db, init_db
from backend.dependencies import get_current_user
from backend import crud, schemas
from backend import ai_service
from backend import file_service
from backend import tools as assistant_tools
from backend.routes.image_routes import router as image_router
from backend.services import ai_router, image_generation, media_store
from backend.services import image_analysis_service as image_analysis
from backend.services.provider_types import (
    MESSAGE_TYPE_IMAGE_ANALYSIS,
    MESSAGE_TYPE_IMAGE_GENERATION,
    MESSAGE_TYPE_TEXT,
    ROUTE_MODE_ANALYZE_IMAGE,
    ROUTE_MODE_CHAT,
    ROUTE_MODE_GENERATE_IMAGE,
    ProviderConfigurationError,
    ProviderRequestError,
)
from backend.utils import SECRET_KEY

# ─── Logging ──────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# ─── Lifespan ─────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    if not SECRET_KEY:
        raise RuntimeError("SECRET_KEY environment variable is required to start the application.")
    media_store.ensure_media_dirs()
    init_db()
    logger.info("=== Jarvis AI Assistant started ===")
    if os.getenv("GROQ_API_KEY"):
        logger.info(
            "AI Service configured | model '%s' | timeout=%.1fs",
            ai_service.MODEL_NAME,
            ai_service.GROQ_TIMEOUT_SECONDS,
        )
    else:
        logger.warning("AI Service is not configured: GROQ_API_KEY is missing.")
    yield
    logger.info("=== Jarvis AI Assistant shutting down ===")

# ─── App ──────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Jarvis AI Assistant",
    description="A personal AI assistant backend powered by FastAPI and SQLite.",
    version="2.0.0",
    lifespan=lifespan,
)

FRONTEND_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")
DIST_DIR = os.path.join(FRONTEND_DIR, "dist")
LEGACY_STATIC = os.path.join(FRONTEND_DIR, "_legacy", "static")
media_store.ensure_media_dirs()
MEDIA_DIR = str(media_store.MEDIA_ROOT)

# Legacy vanilla UI assets (optional), for old bookmarks under /static/*
if os.path.isdir(LEGACY_STATIC):
    app.mount("/static", StaticFiles(directory=LEGACY_STATIC), name="static")

app.mount("/media", StaticFiles(directory=MEDIA_DIR), name="media")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def disable_frontend_caching(request, call_next):
    response = await call_next(request)
    path = request.url.path
    if path == "/app" or path.startswith("/app/") or path.startswith("/static/"):
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response

app.include_router(image_router)
app.include_router(auth_router)


# ─── Root ─────────────────────────────────────────────────────────────────────

@app.get("/", tags=["Health"])
async def root():
    return {"status": "Jarvis running"}


@app.get("/protected", response_model=schemas.ProtectedResponse, tags=["Authentication"])
def protected_route(current_user_id: int = Depends(get_current_user)):
    return schemas.ProtectedResponse(user_id=current_user_id)


# React SPA (Vite build): served from /app with client-side assets under /app/assets/*
if os.path.isdir(DIST_DIR) and os.path.isfile(os.path.join(DIST_DIR, "index.html")):
    app.mount("/app", StaticFiles(directory=DIST_DIR, html=True), name="frontend_spa")
else:
    logger.warning(
        "Frontend build not found at %s — run `npm install` and `npm run build` in frontend/",
        DIST_DIR,
    )

    @app.get("/app", include_in_schema=False)
    async def serve_frontend_missing_build():
        from fastapi.responses import HTMLResponse

        return HTMLResponse(
            "<html><body style='font-family:system-ui;padding:2rem;background:#0f172a;color:#e2e8f0'>"
            "<h1>Jarvis UI not built</h1>"
            "<p>From the project root, run:</p>"
            "<pre style='background:#1e293b;padding:1rem;border-radius:8px'>cd frontend\nnpm install\nnpm run build</pre>"
            "<p>Then restart the server and open <code>/app</code> again.</p>"
            "</body></html>",
            status_code=503,
        )


# ─── Health ───────────────────────────────────────────────────────────────────

@app.get("/api/health", tags=["Health"])
async def health_check():
    return {
        "status": "ok",
        "service": "Jarvis AI Assistant",
        "ai_service": ai_service.check_ai_service(),
        "providers": _provider_health(),
    }


# ─── Chat ─────────────────────────────────────────────────────────────────────

DEFAULT_CHAT_TITLE = "New Chat"
FILE_CHAT_SYSTEM_PROMPT = """You are Jarvis, an intelligent AI assistant analyzing a document.
Answer ONLY using the document context.
If the answer is not found in the document, reply exactly: Not found in document
Use clean formatting."""


def _recent_history(messages, limit: int = 12) -> list[dict[str, str]]:
    history = [{"role": msg.role, "content": msg.content} for msg in messages]
    return history[-limit:] if len(history) > limit else history


def _upload_error_status(detail: str) -> int:
    detail_lower = detail.lower()
    if "too large" in detail_lower:
        return status.HTTP_413_REQUEST_ENTITY_TOO_LARGE
    if "no readable text" in detail_lower:
        return status.HTTP_422_UNPROCESSABLE_ENTITY
    if "failed to read" in detail_lower or "extractable text" in detail_lower:
        return status.HTTP_422_UNPROCESSABLE_ENTITY
    return status.HTTP_400_BAD_REQUEST


def _extract_and_chunk_document(content: bytes, filename: str) -> tuple[str, list[str]]:
    text = file_service.extract_text(content, filename)
    chunks = file_service.chunk_text(text)
    return text, chunks


def _chat_title_from_message(content: str, file_name: str | None = None) -> str:
    trimmed = " ".join(content.split())
    if not trimmed:
        return DEFAULT_CHAT_TITLE
    base = trimmed[:60]
    return f"[{file_name}] {base}"[:255] if file_name else base[:255]


def _metadata_json(metadata: dict | None) -> str | None:
    if not metadata:
        return None
    return json.dumps(metadata)


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


def _provider_health() -> dict:
    return {
        "text_provider": "groq" if os.getenv("GROQ_API_KEY") else "unconfigured",
        "image_provider": os.getenv("IMAGE_PROVIDER_NAME", "pollinations"),
        "vision_provider": os.getenv("VISION_PROVIDER_NAME", image_analysis.DEFAULT_VISION_PROVIDER),
    }


def _get_owned_chat(db: Session, user_id: int, chat_id: int):
    chat = crud.get_user_chat(db, chat_id, user_id)
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found.")
    return chat


def _get_owned_file(db: Session, user_id: int, file_id: str):
    file_doc = crud.get_user_file_document(db, file_id, user_id)
    if not file_doc:
        raise HTTPException(status_code=404, detail="File not found.")
    return file_doc


def _sse_event(event: str, payload: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(payload)}\n\n"


def _chunk_text_for_stream(text: str, chunk_size: int = 28) -> list[str]:
    words = text.split()
    if not words:
        return []
    chunks: list[str] = []
    current = ""
    for word in words:
        candidate = word if not current else f"{current} {word}"
        if len(candidate) > chunk_size and current:
            chunks.append(current)
            current = word
        else:
            current = candidate
    if current:
        chunks.append(current)
    return chunks


async def _prepare_stream_text_reply(
    *,
    db: Session,
    user_id: int,
    chat,
    content: str,
    file_id: str | None = None,
    selected_agent: str = "auto",
    request_mode: str = "auto",
) -> dict | None:
    normalized_content = content.strip()
    normalized_request_mode = ai_router.normalize_mode(request_mode)
    target_file_id = (
        (file_id or chat.document_file_id)
        if normalized_request_mode not in {ROUTE_MODE_GENERATE_IMAGE, ROUTE_MODE_ANALYZE_IMAGE}
        else None
    )
    file_doc = None

    if target_file_id:
        file_doc = _get_owned_file(db, user_id, target_file_id)
        if chat.document_file_id and chat.document_file_id != target_file_id:
            raise HTTPException(status_code=400, detail="This chat is linked to a different document.")
        if not chat.document_file_id:
            chat = crud.update_chat(
                db,
                chat,
                schemas.ChatUpdate(
                    document_file_id=file_doc.file_id,
                    document_filename=file_doc.filename,
                ),
            )

    if file_doc:
        if not normalized_content:
            raise HTTPException(status_code=400, detail="A question is required for document chat.")

        user_msg = crud.create_message(
            db,
            schemas.MessageCreate(
                chat_id=chat.id,
                role="user",
                content=normalized_content,
                message_type=MESSAGE_TYPE_TEXT,
                response_type=MESSAGE_TYPE_TEXT,
            ),
        )
        existing = crud.get_chat_messages(db, chat.id)
        history = _recent_history(existing[:-1], limit=15)

        chunk_rows = crud.get_file_chunks(db, file_doc.file_id)
        if not chunk_rows:
            raise HTTPException(
                status_code=500,
                detail="Document chunks are missing. Please upload the file again.",
            )

        chunk_texts = [chunk.content for chunk in chunk_rows]
        retrieval_query = await asyncio.to_thread(
            file_service.build_retrieval_query,
            content,
            history,
        )
        relevant_chunks = await asyncio.to_thread(
            file_service.retrieve_chunks,
            retrieval_query,
            chunk_texts,
            5,
        )
        context_block = file_service.format_chunks_for_prompt(relevant_chunks)
        groq_messages = [
            {"role": "system", "content": FILE_CHAT_SYSTEM_PROMPT},
            {
                "role": "system",
                "content": f"Document: {file_doc.filename}\n\nContext:\n{context_block}",
            },
            *history,
            {"role": "user", "content": content},
        ]
        base_messages = [
            {"role": "system", "content": FILE_CHAT_SYSTEM_PROMPT},
            {
                "role": "system",
                "content": f"Document: {file_doc.filename}\n\nContext:\n{context_block}",
            },
            *history,
            {"role": "user", "content": content},
        ]
        planning = await asyncio.to_thread(
            ai_service.complete_with_tools,
            messages=base_messages,
            tools=assistant_tools.TOOL_DEFINITIONS,
            failure_message="I couldn't analyze the document right now. Please try again.",
        )
        final_messages = base_messages
        tool_call_summaries: list[dict] = []

        if planning["tool_calls"]:
            final_messages = [
                *base_messages,
                {
                    "role": "assistant",
                    "content": planning["content"] or "",
                    "tool_calls": [
                        {
                            "id": call["id"],
                            "type": "function",
                            "function": {
                                "name": call["name"],
                                "arguments": call["raw_arguments"],
                            },
                        }
                        for call in planning["tool_calls"]
                    ],
                },
            ]
            for call in planning["tool_calls"]:
                result = assistant_tools.execute_tool(
                    call["name"],
                    call["arguments"],
                    assistant_tools.ToolContext(db=db, user_id=user_id),
                )
                tool_call_summaries.append(
                    {
                        "name": call["name"],
                        "arguments": call["arguments"],
                        "result": result,
                    }
                )
                final_messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": call["id"],
                        "name": call["name"],
                        "content": result,
                    }
                )

        return {
            "chat": chat,
            "user_msg": user_msg,
            "groq_messages": final_messages,
            "failure_message": "I couldn't analyze the document right now. Please try again.",
            "agent_type": None,
            "response_metadata": {
                "document_filename": file_doc.filename,
                "tool_calls": tool_call_summaries,
            },
            "response_model": ai_service.MODEL_NAME,
            "provider_name": "groq",
            "prefetched_reply": planning["content"] if not planning["tool_calls"] else None,
        }

    decision = ai_router.decide_route(
        mode=normalized_request_mode,
        text=normalized_content,
        has_image_attachment=False,
    )
    if decision.mode != ROUTE_MODE_CHAT:
        return None

    if not normalized_content:
        raise HTTPException(status_code=400, detail="Message content is required for chat.")

    user_msg = crud.create_message(
        db,
        schemas.MessageCreate(
            chat_id=chat.id,
            role="user",
            content=normalized_content,
            message_type=MESSAGE_TYPE_TEXT,
            response_type=MESSAGE_TYPE_TEXT,
        ),
    )
    existing = crud.get_chat_messages(db, chat.id)
    history = _recent_history(existing[:-1], limit=15)
    agent_type, groq_messages = await asyncio.to_thread(
        ai_service.prepare_agent_messages,
        user_input=normalized_content,
        history=history,
        selected_agent=selected_agent,
    )
    planning = await asyncio.to_thread(
        ai_service.complete_with_tools,
        messages=groq_messages,
        tools=assistant_tools.TOOL_DEFINITIONS,
        failure_message="I couldn't generate a response right now. Please try again.",
    )
    final_messages = groq_messages
    tool_call_summaries: list[dict] = []

    if planning["tool_calls"]:
        final_messages = [
            *groq_messages,
            {
                "role": "assistant",
                "content": planning["content"] or "",
                "tool_calls": [
                    {
                        "id": call["id"],
                        "type": "function",
                        "function": {
                            "name": call["name"],
                            "arguments": call["raw_arguments"],
                        },
                    }
                    for call in planning["tool_calls"]
                ],
            },
        ]
        for call in planning["tool_calls"]:
            result = assistant_tools.execute_tool(
                call["name"],
                call["arguments"],
                assistant_tools.ToolContext(db=db, user_id=user_id),
            )
            tool_call_summaries.append(
                {
                    "name": call["name"],
                    "arguments": call["arguments"],
                    "result": result,
                }
            )
            final_messages.append(
                {
                    "role": "tool",
                    "tool_call_id": call["id"],
                    "name": call["name"],
                    "content": result,
                }
            )

    return {
        "chat": chat,
        "user_msg": user_msg,
        "groq_messages": final_messages,
        "failure_message": "I couldn't generate a response right now. Please try again.",
        "agent_type": agent_type,
        "response_metadata": {
            "route_reason": decision.reason,
            "tool_calls": tool_call_summaries,
        },
        "response_model": ai_service.MODEL_NAME,
        "provider_name": "groq",
        "prefetched_reply": planning["content"] if not planning["tool_calls"] else None,
    }


async def _generate_chat_reply(
    *,
    db: Session,
    user_id: int,
    chat,
    content: str,
    file_id: str | None = None,
    selected_agent: str = "auto",
    request_mode: str = "auto",
    style: str | None = None,
    aspect_ratio: str | None = None,
    size: str | None = None,
    image_upload: UploadFile | None = None,
    image_url: str | None = None,
) -> schemas.ChatMessageResponse:
    normalized_content = content.strip()
    normalized_image_url = (image_url or "").strip() or None
    has_image_attachment = image_upload is not None or normalized_image_url is not None
    normalized_request_mode = ai_router.normalize_mode(request_mode)
    file_doc = None
    agent_type = None
    target_file_id = (
        (file_id or chat.document_file_id)
        if normalized_request_mode not in {ROUTE_MODE_GENERATE_IMAGE, ROUTE_MODE_ANALYZE_IMAGE}
        and not has_image_attachment
        else None
    )
    if target_file_id:
        file_doc = _get_owned_file(db, user_id, target_file_id)
        if chat.document_file_id and chat.document_file_id != target_file_id:
            raise HTTPException(status_code=400, detail="This chat is linked to a different document.")
        if not chat.document_file_id:
            chat = crud.update_chat(
                db,
                chat,
                schemas.ChatUpdate(
                    document_file_id=file_doc.file_id,
                    document_filename=file_doc.filename,
                ),
            )

    if file_doc:
        if not normalized_content:
            raise HTTPException(status_code=400, detail="A question is required for document chat.")

        user_msg = crud.create_message(
            db,
            schemas.MessageCreate(
                chat_id=chat.id,
                role="user",
                content=normalized_content,
                message_type=MESSAGE_TYPE_TEXT,
                response_type=MESSAGE_TYPE_TEXT,
            ),
        )
        existing = crud.get_chat_messages(db, chat.id)
        history = _recent_history(existing[:-1], limit=15)

        chunk_rows = crud.get_file_chunks(db, file_doc.file_id)
        if not chunk_rows:
            raise HTTPException(
                status_code=500,
                detail="Document chunks are missing. Please upload the file again.",
            )

        chunk_texts = [chunk.content for chunk in chunk_rows]
        retrieval_query = await asyncio.to_thread(
            file_service.build_retrieval_query,
            content,
            history,
        )
        relevant_chunks = await asyncio.to_thread(
            file_service.retrieve_chunks,
            retrieval_query,
            chunk_texts,
            5,
        )
        context_block = file_service.format_chunks_for_prompt(relevant_chunks)
        groq_messages = [
            {"role": "system", "content": FILE_CHAT_SYSTEM_PROMPT},
            {
                "role": "system",
                "content": f"Document: {file_doc.filename}\n\nContext:\n{context_block}",
            },
            *history,
            {"role": "user", "content": content},
        ]
        planning = await asyncio.to_thread(
            ai_service.complete_with_tools,
            messages=groq_messages,
            tools=assistant_tools.TOOL_DEFINITIONS,
            failure_message="I couldn't analyze the document right now. Please try again.",
        )
        response_metadata = {"document_filename": file_doc.filename, "tool_calls": []}
        if planning["tool_calls"]:
            final_messages = [
                *groq_messages,
                {
                    "role": "assistant",
                    "content": planning["content"] or "",
                    "tool_calls": [
                        {
                            "id": call["id"],
                            "type": "function",
                            "function": {
                                "name": call["name"],
                                "arguments": call["raw_arguments"],
                            },
                        }
                        for call in planning["tool_calls"]
                    ],
                },
            ]
            for call in planning["tool_calls"]:
                result = assistant_tools.execute_tool(
                    call["name"],
                    call["arguments"],
                    assistant_tools.ToolContext(db=db, user_id=user_id),
                )
                response_metadata["tool_calls"].append(
                    {"name": call["name"], "arguments": call["arguments"], "result": result}
                )
                final_messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": call["id"],
                        "name": call["name"],
                        "content": result,
                    }
                )
            reply = await asyncio.to_thread(
                ai_service.generateResponse,
                final_messages,
                "I couldn't analyze the document right now. Please try again.",
            )
        else:
            reply = planning["content"]
        message_type = MESSAGE_TYPE_TEXT
        provider_name = "groq"
        response_type = MESSAGE_TYPE_TEXT
        response_model = ai_service.MODEL_NAME
        structured_notes = None
        response_image_url = None
        response_attachment_url = None
    else:
        decision = ai_router.decide_route(
            mode=normalized_request_mode,
            text=normalized_content,
            has_image_attachment=has_image_attachment,
        )

        if decision.mode == ROUTE_MODE_CHAT:
            if not normalized_content:
                raise HTTPException(status_code=400, detail="Message content is required for chat.")

            user_msg = crud.create_message(
                db,
                schemas.MessageCreate(
                    chat_id=chat.id,
                    role="user",
                    content=normalized_content,
                    message_type=MESSAGE_TYPE_TEXT,
                    response_type=MESSAGE_TYPE_TEXT,
                ),
            )
            existing = crud.get_chat_messages(db, chat.id)
            history = _recent_history(existing[:-1], limit=15)
            agent_type, groq_messages = await asyncio.to_thread(
                ai_service.prepare_agent_messages,
                user_input=normalized_content,
                history=history,
                selected_agent=selected_agent,
            )
            planning = await asyncio.to_thread(
                ai_service.complete_with_tools,
                messages=groq_messages,
                tools=assistant_tools.TOOL_DEFINITIONS,
                failure_message="I couldn't generate a response right now. Please try again.",
            )
            response_metadata = {"route_reason": decision.reason, "tool_calls": []}
            if planning["tool_calls"]:
                final_messages = [
                    *groq_messages,
                    {
                        "role": "assistant",
                        "content": planning["content"] or "",
                        "tool_calls": [
                            {
                                "id": call["id"],
                                "type": "function",
                                "function": {
                                    "name": call["name"],
                                    "arguments": call["raw_arguments"],
                                },
                            }
                            for call in planning["tool_calls"]
                        ],
                    },
                ]
                for call in planning["tool_calls"]:
                    result = assistant_tools.execute_tool(
                        call["name"],
                        call["arguments"],
                        assistant_tools.ToolContext(db=db, user_id=user_id),
                    )
                    response_metadata["tool_calls"].append(
                        {"name": call["name"], "arguments": call["arguments"], "result": result}
                    )
                    final_messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": call["id"],
                            "name": call["name"],
                            "content": result,
                        }
                    )
                reply = await asyncio.to_thread(
                    ai_service.generateResponse,
                    final_messages,
                    "I couldn't generate a response right now. Please try again.",
                )
            else:
                reply = planning["content"]
            message_type = MESSAGE_TYPE_TEXT
            provider_name = "groq"
            response_type = MESSAGE_TYPE_TEXT
            response_model = ai_service.MODEL_NAME
            structured_notes = None
            response_image_url = None
            response_attachment_url = None
        elif decision.mode == ROUTE_MODE_GENERATE_IMAGE:
            if not normalized_content:
                raise HTTPException(status_code=400, detail="An image prompt is required.")

            try:
                generation_result = await asyncio.to_thread(
                    image_generation.generate_image,
                    prompt=normalized_content,
                    style=style,
                    aspect_ratio=aspect_ratio,
                    size=size,
                )
            except (ProviderRequestError, ProviderConfigurationError) as exc:
                raise HTTPException(status_code=_provider_error_status(str(exc)), detail=str(exc)) from exc

            user_msg = crud.create_message(
                db,
                schemas.MessageCreate(
                    chat_id=chat.id,
                    role="user",
                    content=normalized_content,
                    message_type=MESSAGE_TYPE_IMAGE_GENERATION,
                    response_type=MESSAGE_TYPE_IMAGE_GENERATION,
                    metadata_json=_metadata_json(
                        {
                            "style": style,
                            "aspect_ratio": aspect_ratio,
                            "size": size,
                        }
                    ),
                ),
            )
            reply = "Generated an image from your prompt."
            message_type = MESSAGE_TYPE_IMAGE_GENERATION
            provider_name = generation_result.provider
            response_type = MESSAGE_TYPE_IMAGE_GENERATION
            response_model = generation_result.model
            response_metadata = {
                "prompt": generation_result.prompt,
                "route_reason": decision.reason,
                **generation_result.metadata,
            }
            structured_notes = None
            response_image_url = generation_result.image_url
            response_attachment_url = None
        elif decision.mode == ROUTE_MODE_ANALYZE_IMAGE:
            if not has_image_attachment:
                raise HTTPException(status_code=400, detail="Attach an image or provide an image URL to analyze.")

            image_bytes = await image_upload.read() if image_upload else None
            try:
                analysis_result = await asyncio.to_thread(
                    image_analysis.analyze_image,
                    question=normalized_content,
                    image_bytes=image_bytes,
                    image_url=normalized_image_url,
                    filename=image_upload.filename if image_upload else None,
                    content_type=image_upload.content_type if image_upload else None,
                )
            except (ProviderRequestError, ProviderConfigurationError) as exc:
                raise HTTPException(status_code=_provider_error_status(str(exc)), detail=str(exc)) from exc

            user_msg = crud.create_message(
                db,
                schemas.MessageCreate(
                    chat_id=chat.id,
                    role="user",
                    content=normalized_content or "Analyze this image.",
                    message_type=MESSAGE_TYPE_IMAGE_ANALYSIS,
                    attachment_url=analysis_result.attachment_url,
                    response_type=MESSAGE_TYPE_IMAGE_ANALYSIS,
                ),
            )
            reply = analysis_result.analysis
            message_type = MESSAGE_TYPE_IMAGE_ANALYSIS
            provider_name = analysis_result.provider
            response_type = MESSAGE_TYPE_IMAGE_ANALYSIS
            response_model = analysis_result.model
            response_metadata = {"route_reason": decision.reason, **analysis_result.metadata}
            structured_notes = analysis_result.structured_notes
            response_image_url = None
            response_attachment_url = analysis_result.attachment_url
        else:
            raise HTTPException(status_code=400, detail="Unsupported request mode.")

    assistant_msg = crud.create_message(
        db,
        schemas.MessageCreate(
            chat_id=chat.id,
            role="assistant",
            agent_type=agent_type,
            content=reply,
            message_type=message_type,
            image_url=response_image_url,
            attachment_url=response_attachment_url,
            provider=provider_name,
            response_type=response_type,
            metadata_json=_metadata_json(response_metadata),
        ),
    )

    if chat.title == DEFAULT_CHAT_TITLE:
        chat = crud.update_chat(
            db,
            chat,
            schemas.ChatUpdate(
                title=_chat_title_from_message(
                    normalized_content or "Image analysis",
                    chat.document_filename,
                )
            ),
        )
    else:
        chat = crud.touch_chat(db, chat)

    logger.info("✓ Chat | chat_id=%d | user_id=%d | reply_len=%d", chat.id, user_id, len(reply))
    return schemas.ChatMessageResponse(
        reply=reply,
        chat_id=chat.id,
        user_message_id=user_msg.id,
        assistant_message_id=assistant_msg.id,
        agent_type=agent_type,
        model=response_model,
        message_type=message_type,
        provider=provider_name,
        response_type=response_type,
        image_url=response_image_url,
        attachment_url=response_attachment_url,
        metadata=response_metadata,
        structured_notes=structured_notes,
    )


@app.post("/api/chat/create", response_model=schemas.ChatOut, status_code=status.HTTP_201_CREATED, tags=["Chat"])
def create_chat(
    payload: schemas.ChatCreateRequest,
    current_user_id: int = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return crud.create_chat(db, current_user_id, payload)


@app.get("/api/chats", response_model=List[schemas.ChatOut], tags=["Chat"])
def list_chats(
    skip: int = 0,
    limit: int = 50,
    current_user_id: int = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return crud.get_user_chats(db, current_user_id, skip=skip, limit=limit)


@app.get("/api/chat/{chat_id}", response_model=List[schemas.MessageOut], tags=["Chat"])
def get_chat_messages(
    chat_id: int,
    current_user_id: int = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    chat = _get_owned_chat(db, current_user_id, chat_id)
    return crud.get_chat_messages(db, chat.id)


@app.post("/api/chat/{chat_id}/message", response_model=schemas.ChatMessageResponse, tags=["Chat"])
async def post_chat_message(
    chat_id: int,
    payload: schemas.ChatMessageRequest,
    current_user_id: int = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    logger.info(
        "POST /api/chat/%s/message | user_id=%s | agent=%s | msg='%.60s'...",
        chat_id,
        current_user_id,
        payload.selected_agent,
        payload.content,
    )
    chat = _get_owned_chat(db, current_user_id, chat_id)
    return await _generate_chat_reply(
        db=db,
        user_id=current_user_id,
        chat=chat,
        content=payload.content,
        file_id=payload.file_id,
        selected_agent=payload.selected_agent,
        request_mode=payload.request_mode,
        style=payload.style,
        aspect_ratio=payload.aspect_ratio,
        size=payload.size,
    )


@app.post("/api/chat/{chat_id}/message/stream", tags=["Chat"])
async def stream_chat_message(
    chat_id: int,
    payload: schemas.ChatMessageRequest,
    request: Request,
    current_user_id: int = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    chat = _get_owned_chat(db, current_user_id, chat_id)
    stream_context = await _prepare_stream_text_reply(
        db=db,
        user_id=current_user_id,
        chat=chat,
        content=payload.content,
        file_id=payload.file_id,
        selected_agent=payload.selected_agent,
        request_mode=payload.request_mode,
    )

    headers = {
        "Cache-Control": "no-cache, no-store, must-revalidate",
        "Pragma": "no-cache",
        "Expires": "0",
        "X-Accel-Buffering": "no",
    }

    if stream_context is None:
        result = await _generate_chat_reply(
            db=db,
            user_id=current_user_id,
            chat=chat,
            content=payload.content,
            file_id=payload.file_id,
            selected_agent=payload.selected_agent,
            request_mode=payload.request_mode,
            style=payload.style,
            aspect_ratio=payload.aspect_ratio,
            size=payload.size,
        )

        async def single_result_stream():
            yield _sse_event(
                "start",
                {
                    "chat_id": result.chat_id,
                    "user_message_id": result.user_message_id,
                    "message_type": result.message_type,
                    "agent_type": result.agent_type,
                },
            )
            yield _sse_event("final", result.model_dump())

        return StreamingResponse(single_result_stream(), media_type="text/event-stream", headers=headers)

    async def event_stream():
        loop = asyncio.get_running_loop()
        queue: asyncio.Queue[tuple[str, str | None]] = asyncio.Queue()
        parts: list[str] = []
        stop_event = threading.Event()
        client_disconnected = False

        def producer():
            try:
                for delta in ai_service.stream_response_from_messages(
                    stream_context["groq_messages"],
                    stream_context["failure_message"],
                    stop_event=stop_event,
                ):
                    parts.append(delta)
                    loop.call_soon_threadsafe(queue.put_nowait, ("chunk", delta))
            finally:
                loop.call_soon_threadsafe(queue.put_nowait, ("done", None))

        yield _sse_event(
            "start",
            {
                "chat_id": stream_context["chat"].id,
                "user_message_id": stream_context["user_msg"].id,
                "message_type": MESSAGE_TYPE_TEXT,
                "agent_type": stream_context["agent_type"],
                "provider": stream_context["provider_name"],
                "model": stream_context["response_model"],
                "tool_calls": stream_context["response_metadata"].get("tool_calls", []),
            },
        )

        try:
            if stream_context.get("prefetched_reply"):
                for delta in _chunk_text_for_stream(stream_context["prefetched_reply"]):
                    if await request.is_disconnected():
                        client_disconnected = True
                        break
                    parts.append(delta)
                    yield _sse_event("chunk", {"delta": f"{delta} "})
                    await asyncio.sleep(0.015)
            else:
                producer_thread = threading.Thread(target=producer, daemon=True)
                producer_thread.start()
                while True:
                    kind, payload_text = await queue.get()
                    if await request.is_disconnected():
                        client_disconnected = True
                        stop_event.set()
                        break
                    if kind == "chunk" and payload_text:
                        yield _sse_event("chunk", {"delta": payload_text})
                        if await request.is_disconnected():
                            client_disconnected = True
                            stop_event.set()
                            break
                        continue
                    break
        except asyncio.CancelledError:
            client_disconnected = True
            stop_event.set()

        reply = "".join(parts).strip() or stream_context["failure_message"]
        assistant_msg = None
        if reply:
            assistant_msg = crud.create_message(
                db,
                schemas.MessageCreate(
                    chat_id=stream_context["chat"].id,
                    role="assistant",
                    agent_type=stream_context["agent_type"],
                    content=reply,
                    message_type=MESSAGE_TYPE_TEXT,
                    provider=stream_context["provider_name"],
                    response_type=MESSAGE_TYPE_TEXT,
                    metadata_json=_metadata_json(
                        {
                            **stream_context["response_metadata"],
                            "stopped": client_disconnected,
                        }
                    ),
                ),
            )

        current_chat = _get_owned_chat(db, current_user_id, stream_context["chat"].id)

        if current_chat.title == DEFAULT_CHAT_TITLE:
            chat_after = crud.update_chat(
                db,
                current_chat,
                schemas.ChatUpdate(
                    title=_chat_title_from_message(
                        payload.content or "New chat",
                        current_chat.document_filename,
                    )
                ),
            )
        else:
            chat_after = crud.touch_chat(db, current_chat)

        if client_disconnected:
            return

        result = schemas.ChatMessageResponse(
            reply=reply,
            chat_id=chat_after.id,
            user_message_id=stream_context["user_msg"].id,
            assistant_message_id=assistant_msg.id if assistant_msg else 0,
            agent_type=stream_context["agent_type"],
            model=stream_context["response_model"],
            message_type=MESSAGE_TYPE_TEXT,
            provider=stream_context["provider_name"],
            response_type=MESSAGE_TYPE_TEXT,
            image_url=None,
            attachment_url=None,
            metadata={**stream_context["response_metadata"], "stopped": False},
            structured_notes=None,
        )
        yield _sse_event("final", result.model_dump())

    return StreamingResponse(event_stream(), media_type="text/event-stream", headers=headers)


@app.post("/api/chat/{chat_id}/message/multimodal", response_model=schemas.ChatMessageResponse, tags=["Chat"])
async def post_multimodal_chat_message(
    chat_id: int,
    content: str = Form(default=""),
    request_mode: str = Form(default="auto"),
    selected_agent: str = Form(default="auto"),
    style: str | None = Form(default=None),
    aspect_ratio: str | None = Form(default=None),
    size: str | None = Form(default=None),
    image: UploadFile | None = File(default=None),
    image_url: str | None = Form(default=None),
    current_user_id: int = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    chat = _get_owned_chat(db, current_user_id, chat_id)
    return await _generate_chat_reply(
        db=db,
        user_id=current_user_id,
        chat=chat,
        content=content,
        selected_agent=selected_agent,
        request_mode=request_mode,
        style=style,
        aspect_ratio=aspect_ratio,
        size=size,
        image_upload=image,
        image_url=image_url,
    )


@app.delete("/api/chat/{chat_id}", tags=["Chat"])
def delete_chat(
    chat_id: int,
    current_user_id: int = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    chat = _get_owned_chat(db, current_user_id, chat_id)
    crud.delete_chat(db, chat)
    return {"message": "Chat deleted successfully."}


@app.post("/api/chat", response_model=schemas.ChatResponse, tags=["Chat"])
async def legacy_chat(
    request: schemas.ChatRequest,
    current_user_id: int = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    logger.info(
        "POST /api/chat | chat_id=%s | user_id=%s | agent=%s | msg='%.60s'...",
        request.conversation_id,
        current_user_id,
        request.selected_agent,
        request.message,
    )
    chat = (
        _get_owned_chat(db, current_user_id, request.conversation_id)
        if request.conversation_id
        else crud.create_chat(db, current_user_id, schemas.ChatCreateRequest())
    )
    result = await _generate_chat_reply(
        db=db,
        user_id=current_user_id,
        chat=chat,
        content=request.message,
        selected_agent=request.selected_agent,
        request_mode=request.request_mode,
    )
    return schemas.ChatResponse(
        reply=result.reply,
        conversation_id=result.chat_id,
        message_id=result.assistant_message_id,
        agent_type=result.agent_type,
        model=result.model,
        message_type=result.message_type,
        provider=result.provider,
        response_type=result.response_type,
        image_url=result.image_url,
        attachment_url=result.attachment_url,
        metadata=result.metadata,
    )


# ─── File Upload ──────────────────────────────────────────────────────────────

@app.post("/api/upload", response_model=schemas.UploadResponse, tags=["Files"])
async def upload_file(
    file: UploadFile = File(...),
    current_user_id: int = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Upload a PDF or TXT file and store extracted document chunks."""
    original_name = file.filename or "upload"
    content = await file.read()
    try:
        ext = file_service.validate_upload(original_name, file.content_type, content)
        text, chunks = await asyncio.to_thread(
            _extract_and_chunk_document,
            content,
            original_name,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=_upload_error_status(str(exc)),
            detail=str(exc),
        ) from exc

    if not text.strip():
        raise HTTPException(status_code=422, detail="No readable text found in the file.")

    if not chunks:
        raise HTTPException(status_code=422, detail="Document is too short to process.")

    logger.info(
        "Upload: user_id=%s | '%s' | %d bytes | %d chunks",
        current_user_id,
        original_name,
        len(content),
        len(chunks),
    )

    file_id = str(uuid.uuid4())
    crud.create_file_document(
        db, user_id=current_user_id, file_id=file_id, filename=original_name,
        file_type=ext, chunk_count=len(chunks),
    )
    chunk_rows = [
        (i, chunk_text, b"")
        for i, chunk_text in enumerate(chunks)
    ]
    crud.create_file_chunks(db, file_id=file_id, chunks=chunk_rows)

    logger.info("✓ Stored file_id=%s | %d chunks", file_id, len(chunks))
    return schemas.UploadResponse(
        file_id=file_id,
        filename=original_name,
        file_type=ext,
        chunk_count=len(chunks),
    )


# ─── File Chat ────────────────────────────────────────────────────────────────

@app.post("/api/file-chat", response_model=schemas.ChatResponse, tags=["Files"])
async def file_chat(
    request: schemas.FileChatRequest,
    current_user_id: int = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Backward-compatible document chat endpoint routed through user-owned chats."""
    logger.info("POST /api/file-chat | file_id=%s | user_id=%s | query='%.60s'...", request.file_id, current_user_id, request.query)
    chat = (
        _get_owned_chat(db, current_user_id, request.conversation_id)
        if request.conversation_id
        else crud.create_chat(db, current_user_id, schemas.ChatCreateRequest())
    )
    result = await _generate_chat_reply(
        db=db,
        user_id=current_user_id,
        chat=chat,
        content=request.query,
        file_id=request.file_id,
    )
    return schemas.ChatResponse(
        reply=result.reply,
        conversation_id=result.chat_id,
        message_id=result.assistant_message_id,
        agent_type=result.agent_type,
        model=result.model,
        message_type=result.message_type,
        provider=result.provider,
        response_type=result.response_type,
        image_url=result.image_url,
        attachment_url=result.attachment_url,
        metadata=result.metadata,
    )


# ─── Files list / delete ──────────────────────────────────────────────────────

@app.get("/api/files", response_model=List[schemas.FileDocumentOut], tags=["Files"])
def list_files(current_user_id: int = Depends(get_current_user), db: Session = Depends(get_db)):
    """List all uploaded file documents."""
    return crud.get_user_file_documents(db, current_user_id)


@app.delete("/api/files/{file_id}", tags=["Files"])
def delete_file(file_id: str, current_user_id: int = Depends(get_current_user), db: Session = Depends(get_db)):
    """Delete a file document and all its chunks."""
    deleted = crud.delete_user_file_document(db, file_id, current_user_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="File not found.")
    return {"message": "File deleted successfully."}


# ─── Conversations API ────────────────────────────────────────────────────────

@app.get("/api/conversations", response_model=List[schemas.ChatOut], tags=["Conversations"])
def list_conversations(
    skip: int = 0,
    limit: int = 50,
    current_user_id: int = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return crud.get_user_chats(db, current_user_id, skip=skip, limit=limit)


@app.get("/api/conversations/{conversation_id}", response_model=schemas.ChatOut, tags=["Conversations"])
def get_conversation(
    conversation_id: int,
    current_user_id: int = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return _get_owned_chat(db, current_user_id, conversation_id)


@app.post("/api/conversations", response_model=schemas.ChatOut, status_code=status.HTTP_201_CREATED, tags=["Conversations"])
def create_conversation(
    data: schemas.ChatCreateRequest,
    current_user_id: int = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return crud.create_chat(db, current_user_id, data)


@app.patch("/api/conversations/{conversation_id}", response_model=schemas.ChatOut, tags=["Conversations"])
def update_conversation(
    conversation_id: int,
    data: schemas.ChatUpdate,
    current_user_id: int = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    chat = _get_owned_chat(db, current_user_id, conversation_id)
    return crud.update_chat(db, chat, data)


@app.delete("/api/conversations/{conversation_id}", tags=["Conversations"])
def delete_conversation(
    conversation_id: int,
    current_user_id: int = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    chat = _get_owned_chat(db, current_user_id, conversation_id)
    crud.delete_chat(db, chat)
    return {"message": "Conversation deleted successfully."}


# ─── Messages API ─────────────────────────────────────────────────────────────

@app.get("/api/conversations/{conversation_id}/messages", response_model=List[schemas.MessageOut], tags=["Messages"])
def list_messages(
    conversation_id: int,
    current_user_id: int = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    chat = _get_owned_chat(db, current_user_id, conversation_id)
    return crud.get_chat_messages(db, chat.id)


# ─── Notes API ────────────────────────────────────────────────────────────────

@app.get("/api/notes", response_model=List[schemas.NoteOut], tags=["Notes"])
def list_notes(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return crud.get_notes(db, skip=skip, limit=limit)


@app.get("/api/notes/{note_id}", response_model=schemas.NoteOut, tags=["Notes"])
def get_note(note_id: int, db: Session = Depends(get_db)):
    obj = crud.get_note(db, note_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Note not found.")
    return obj


@app.post("/api/notes", response_model=schemas.NoteOut, status_code=status.HTTP_201_CREATED, tags=["Notes"])
def create_note(data: schemas.NoteCreate, db: Session = Depends(get_db)):
    return crud.create_note(db, data)


@app.patch("/api/notes/{note_id}", response_model=schemas.NoteOut, tags=["Notes"])
def update_note(note_id: int, data: schemas.NoteUpdate, db: Session = Depends(get_db)):
    obj = crud.update_note(db, note_id, data)
    if not obj:
        raise HTTPException(status_code=404, detail="Note not found.")
    return obj


@app.delete("/api/notes/{note_id}", tags=["Notes"])
def delete_note(note_id: int, db: Session = Depends(get_db)):
    crud.delete_note(db, note_id)
    return {"message": "Note deleted successfully."}
