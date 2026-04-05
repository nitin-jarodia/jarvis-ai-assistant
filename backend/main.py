"""
Jarvis AI Assistant — FastAPI main application.
Run with: uvicorn backend.main:app --reload
      or: python run.py
"""

import asyncio
import os
import uuid
import logging
from contextlib import asynccontextmanager
from typing import List

from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, status
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from backend.auth import router as auth_router
from backend.database import get_db, init_db
from backend.dependencies import get_current_user
from backend import crud, schemas
from backend import ai_service
from backend import file_service
from backend.routes.image_routes import router as image_router
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
STATIC_DIR   = os.path.join(FRONTEND_DIR, "static")

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

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
    if request.url.path == "/app" or request.url.path.startswith("/static/"):
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


@app.get("/app", include_in_schema=False)
async def serve_frontend():
    return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))


# ─── Health ───────────────────────────────────────────────────────────────────

@app.get("/api/health", tags=["Health"])
async def health_check():
    return {
        "status": "ok",
        "service": "Jarvis AI Assistant",
        "ai_service": ai_service.check_ai_service(),
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


async def _generate_chat_reply(
    *,
    db: Session,
    user_id: int,
    chat,
    content: str,
    file_id: str | None = None,
) -> schemas.ChatMessageResponse:
    file_doc = None
    agent_type = None
    target_file_id = file_id or chat.document_file_id
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

    user_msg = crud.create_message(
        db,
        schemas.MessageCreate(chat_id=chat.id, role="user", content=content),
    )
    existing = crud.get_chat_messages(db, chat.id)
    history = _recent_history(existing[:-1], limit=15)

    if file_doc:
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
        reply = await asyncio.to_thread(
            ai_service.generate_response_from_messages,
            groq_messages,
            "I couldn't analyze the document right now. Please try again.",
        )
    else:
        agent_type, reply = await asyncio.to_thread(
            ai_service.generate_agent_response,
            user_input=content,
            history=history,
        )

    assistant_msg = crud.create_message(
        db,
        schemas.MessageCreate(
            chat_id=chat.id,
            role="assistant",
            agent_type=agent_type,
            content=reply,
        ),
    )

    if chat.title == DEFAULT_CHAT_TITLE:
        chat = crud.update_chat(
            db,
            chat,
            schemas.ChatUpdate(title=_chat_title_from_message(content, chat.document_filename)),
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
        model=ai_service.MODEL_NAME,
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
    logger.info("POST /api/chat/%s/message | user_id=%s | msg='%.60s'...", chat_id, current_user_id, payload.content)
    chat = _get_owned_chat(db, current_user_id, chat_id)
    return await _generate_chat_reply(
        db=db,
        user_id=current_user_id,
        chat=chat,
        content=payload.content,
        file_id=payload.file_id,
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
    logger.info("POST /api/chat | chat_id=%s | user_id=%s | msg='%.60s'...", request.conversation_id, current_user_id, request.message)
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
    )
    return schemas.ChatResponse(
        reply=result.reply,
        conversation_id=result.chat_id,
        message_id=result.assistant_message_id,
        agent_type=result.agent_type,
        model=result.model,
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
