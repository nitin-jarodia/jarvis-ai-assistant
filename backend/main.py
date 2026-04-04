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

from backend.database import get_db, init_db
from backend import crud, schemas
from backend import ai_service
from backend import file_service
from backend.routes.image_routes import router as image_router

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


# ─── Root ─────────────────────────────────────────────────────────────────────

@app.get("/", tags=["Health"])
async def root():
    return {"status": "Jarvis running"}


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

@app.post("/api/chat", response_model=schemas.ChatResponse, tags=["Chat"])
async def chat(request: schemas.ChatRequest, db: Session = Depends(get_db)):
    """Standard chat endpoint — no file context."""
    logger.info("POST /api/chat | conv_id=%s | msg='%.60s'...", request.conversation_id, request.message)

    if request.conversation_id:
        convo = crud.get_conversation(db, request.conversation_id)
        if not convo:
            raise HTTPException(status_code=404, detail="Conversation not found.")
    else:
        convo = crud.create_conversation(db, schemas.ConversationCreate(title=request.message[:60]))

    crud.create_message(db, schemas.MessageCreate(
        conversation_id=convo.id, role="user", content=request.message,
    ))

    existing = crud.get_messages(db, convo.id)
    history  = [{"role": m.role, "content": m.content} for m in existing[:-1]]
    if len(history) > 15:
        history = history[-15:]

    reply = await asyncio.to_thread(
        ai_service.generate_response,
        request.message,
        history,
    )

    assistant_msg = crud.create_message(db, schemas.MessageCreate(
        conversation_id=convo.id, role="assistant", content=reply,
    ))

    logger.info("✓ Chat | conv_id=%d | reply_len=%d", convo.id, len(reply))
    return schemas.ChatResponse(
        reply=reply,
        conversation_id=convo.id,
        message_id=assistant_msg.id,
        model=ai_service.MODEL_NAME,
    )


# ─── File Upload ──────────────────────────────────────────────────────────────

def _upload_error_status(detail: str) -> int:
    detail_lower = detail.lower()
    if "too large" in detail_lower:
        return status.HTTP_413_REQUEST_ENTITY_TOO_LARGE
    if "no readable text" in detail_lower:
        return status.HTTP_422_UNPROCESSABLE_ENTITY
    if "failed to read" in detail_lower or "extractable text" in detail_lower:
        return status.HTTP_422_UNPROCESSABLE_ENTITY
    return status.HTTP_400_BAD_REQUEST


def _recent_history(messages, limit: int = 8) -> list[dict[str, str]]:
    history = [{"role": msg.role, "content": msg.content} for msg in messages]
    return history[-limit:] if len(history) > limit else history


def _extract_and_chunk_document(content: bytes, filename: str) -> tuple[str, list[str]]:
    text = file_service.extract_text(content, filename)
    chunks = file_service.chunk_text(text)
    return text, chunks

@app.post("/api/upload", response_model=schemas.UploadResponse, tags=["Files"])
async def upload_file(file: UploadFile = File(...), db: Session = Depends(get_db)):
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
        "Upload: '%s' | %d bytes | %d chunks",
        original_name,
        len(content),
        len(chunks),
    )

    file_id = str(uuid.uuid4())
    crud.create_file_document(
        db, file_id=file_id, filename=original_name,
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

FILE_CHAT_SYSTEM_PROMPT = """You are Jarvis, an intelligent AI assistant analyzing a document.
Answer ONLY using the document context.
If the answer is not found in the document, reply exactly: Not found in document
Use clean formatting."""


@app.post("/api/file-chat", response_model=schemas.ChatResponse, tags=["Files"])
async def file_chat(request: schemas.FileChatRequest, db: Session = Depends(get_db)):
    """Chat with a specific uploaded document using chunk retrieval."""
    logger.info("POST /api/file-chat | file_id=%s | query='%.60s'...", request.file_id, request.query)

    file_doc = crud.get_file_document(db, request.file_id)
    if not file_doc:
        raise HTTPException(status_code=404, detail="File not found. Please upload it again.")

    if request.conversation_id:
        convo = crud.get_conversation(db, request.conversation_id)
        if not convo:
            raise HTTPException(status_code=404, detail="Conversation not found.")
        if convo.document_file_id and convo.document_file_id != request.file_id:
            raise HTTPException(status_code=400, detail="This conversation is linked to a different document.")
        if not convo.document_file_id:
            convo = crud.update_conversation(
                db,
                convo.id,
                schemas.ConversationUpdate(
                    document_file_id=file_doc.file_id,
                    document_filename=file_doc.filename,
                ),
            )
    else:
        title = f"[{file_doc.filename}] {request.query[:50]}"
        convo = crud.create_conversation(
            db,
            schemas.ConversationCreate(
                title=title,
                document_file_id=file_doc.file_id,
                document_filename=file_doc.filename,
            ),
        )

    crud.create_message(db, schemas.MessageCreate(
        conversation_id=convo.id, role="user", content=request.query,
    ))

    chunk_rows = crud.get_file_chunks(db, request.file_id)
    if not chunk_rows:
        raise HTTPException(
            status_code=500,
            detail="Document chunks are missing. Please upload the file again.",
        )

    chunk_texts = [chunk.content for chunk in chunk_rows]
    existing = crud.get_messages(db, convo.id)
    history = _recent_history(existing[:-1], limit=10)
    retrieval_query = await asyncio.to_thread(
        file_service.build_retrieval_query,
        request.query,
        history,
    )
    relevant_chunks = await asyncio.to_thread(
        file_service.retrieve_chunks,
        retrieval_query,
        chunk_texts,
        5,
    )
    context_block = file_service.format_chunks_for_prompt(relevant_chunks)
    messages = [
        {"role": "system", "content": FILE_CHAT_SYSTEM_PROMPT},
        {
            "role": "system",
            "content": f"Document: {file_doc.filename}\n\nContext:\n{context_block}",
        },
        *history,
        {"role": "user", "content": request.query},
    ]
    reply = await asyncio.to_thread(
        ai_service.generate_response_from_messages,
        messages,
        "I couldn't analyze the document right now. Please try again.",
    )

    assistant_msg = crud.create_message(db, schemas.MessageCreate(
        conversation_id=convo.id, role="assistant", content=reply,
    ))

    logger.info(
        "✓ File-chat | file_id=%s | chunks_used=%d | reply_len=%d",
        request.file_id, len(relevant_chunks), len(reply),
    )
    return schemas.ChatResponse(
        reply=reply,
        conversation_id=convo.id,
        message_id=assistant_msg.id,
        model=ai_service.MODEL_NAME,
    )


# ─── Files list / delete ──────────────────────────────────────────────────────

@app.get("/api/files", response_model=List[schemas.FileDocumentOut], tags=["Files"])
def list_files(db: Session = Depends(get_db)):
    """List all uploaded file documents."""
    return crud.get_file_documents(db)


@app.delete("/api/files/{file_id}", tags=["Files"])
def delete_file(file_id: str, db: Session = Depends(get_db)):
    """Delete a file document and all its chunks."""
    deleted = crud.delete_file_document(db, file_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="File not found.")
    return {"message": "File deleted successfully."}


# ─── Conversations API ────────────────────────────────────────────────────────

@app.get("/api/conversations", response_model=List[schemas.ConversationOut], tags=["Conversations"])
def list_conversations(skip: int = 0, limit: int = 50, db: Session = Depends(get_db)):
    return crud.get_conversations(db, skip=skip, limit=limit)


@app.get("/api/conversations/{conversation_id}", response_model=schemas.ConversationOut, tags=["Conversations"])
def get_conversation(conversation_id: int, db: Session = Depends(get_db)):
    obj = crud.get_conversation(db, conversation_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Conversation not found.")
    return obj


@app.post("/api/conversations", response_model=schemas.ConversationOut, status_code=status.HTTP_201_CREATED, tags=["Conversations"])
def create_conversation(data: schemas.ConversationCreate, db: Session = Depends(get_db)):
    return crud.create_conversation(db, data)


@app.patch("/api/conversations/{conversation_id}", response_model=schemas.ConversationOut, tags=["Conversations"])
def update_conversation(conversation_id: int, data: schemas.ConversationUpdate, db: Session = Depends(get_db)):
    obj = crud.update_conversation(db, conversation_id, data)
    if not obj:
        raise HTTPException(status_code=404, detail="Conversation not found.")
    return obj


@app.delete("/api/conversations/{conversation_id}", tags=["Conversations"])
def delete_conversation(conversation_id: int, db: Session = Depends(get_db)):
    crud.delete_conversation(db, conversation_id)
    return {"message": "Conversation archived successfully."}


# ─── Messages API ─────────────────────────────────────────────────────────────

@app.get("/api/conversations/{conversation_id}/messages", response_model=List[schemas.MessageOut], tags=["Messages"])
def list_messages(conversation_id: int, db: Session = Depends(get_db)):
    convo = crud.get_conversation(db, conversation_id)
    if not convo:
        raise HTTPException(status_code=404, detail="Conversation not found.")
    return crud.get_messages(db, conversation_id)


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
