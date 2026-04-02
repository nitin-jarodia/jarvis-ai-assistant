"""
Jarvis AI Assistant — FastAPI main application.
Run with: uvicorn backend.main:app --reload
      or: python run.py
"""

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

# ─── Logging ──────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# ─── Configuration ─────────────────────────────────────────────────────────────

MAX_UPLOAD_BYTES = 10 * 1024 * 1024   # 10 MB
ALLOWED_EXTENSIONS = {"pdf", "txt"}

# ─── Lifespan ─────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    logger.info("=== Jarvis AI Assistant started ===")
    ai_info = ai_service.check_ai_service()
    if ai_info["status"] == "ok":
        logger.info("AI Service: Ready | model '%s'", ai_service.MODEL_NAME)
    else:
        logger.warning("AI Service Error: %s", ai_info.get("detail", "Unknown"))
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


# ─── Root ─────────────────────────────────────────────────────────────────────

@app.get("/", include_in_schema=False)
def serve_frontend():
    return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))


# ─── Health ───────────────────────────────────────────────────────────────────

@app.get("/api/health", tags=["Health"])
def health_check():
    return {
        "status": "ok",
        "service": "Jarvis AI Assistant",
        "ai_service": ai_service.check_ai_service(),
    }


# ─── Chat ─────────────────────────────────────────────────────────────────────

@app.post("/api/chat", response_model=schemas.ChatResponse, tags=["Chat"])
def chat(request: schemas.ChatRequest, db: Session = Depends(get_db)):
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

    reply = ai_service.generate_response(request.message, history=history)

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

@app.post("/api/upload", response_model=schemas.UploadResponse, tags=["Files"])
async def upload_file(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """
    Upload a PDF or TXT file.
    - Validates type and size
    - Extracts text, chunks it, embeds each chunk, stores in DB
    - Returns a file_id for subsequent /api/file-chat calls
    """
    # Validate file extension
    original_name = file.filename or "upload"
    ext = original_name.rsplit(".", 1)[-1].lower() if "." in original_name else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '.{ext}'. Allowed: PDF, TXT.",
        )

    # Read and validate size
    content = await file.read()
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File too large ({len(content) // 1024} KB). Maximum is 10 MB.",
        )
    if len(content) == 0:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    logger.info("Upload: '%s' | %d bytes | type=%s", original_name, len(content), ext)

    # Extract text
    try:
        text = file_service.extract_text(content, original_name)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    if not text.strip():
        raise HTTPException(status_code=422, detail="No readable text found in the file.")

    # Chunk text
    chunks = file_service.chunk_text(text)
    if not chunks:
        raise HTTPException(status_code=422, detail="Document is too short to process.")

    logger.info("Chunked '%s' into %d chunks. Embedding…", original_name, len(chunks))

    # Embed all chunks
    try:
        embeddings = file_service.embed_texts(chunks)
    except Exception as e:
        logger.error("Embedding failed: %s", e)
        raise HTTPException(status_code=500, detail="Failed to process document embeddings.")

    # Persist metadata + chunks
    file_id = str(uuid.uuid4())
    crud.create_file_document(
        db, file_id=file_id, filename=original_name,
        file_type=ext, chunk_count=len(chunks),
    )

    chunk_rows = [
        (i, text, file_service.embedding_to_bytes(embeddings[i]))
        for i, text in enumerate(chunks)
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

Rules:
- Answer ONLY using the document context provided below.
- If the answer is not in the context, say: "I couldn't find that information in the document."
- Quote or reference specific parts of the document when helpful.
- Be concise, accurate, and well-formatted.
- Use bullet points, headings, or code blocks where appropriate."""


@app.post("/api/file-chat", response_model=schemas.ChatResponse, tags=["Files"])
def file_chat(request: schemas.FileChatRequest, db: Session = Depends(get_db)):
    """
    Chat with a specific uploaded document using RAG.
    - Retrieves top-k semantically similar chunks
    - Combines with conversation history
    - Returns a grounded, document-aware response
    """
    logger.info("POST /api/file-chat | file_id=%s | query='%.60s'...", request.file_id, request.query)

    # Validate file exists
    file_doc = crud.get_file_document(db, request.file_id)
    if not file_doc:
        raise HTTPException(status_code=404, detail="File not found. Please upload it again.")

    # Get or create conversation
    if request.conversation_id:
        convo = crud.get_conversation(db, request.conversation_id)
        if not convo:
            raise HTTPException(status_code=404, detail="Conversation not found.")
    else:
        title = f"[{file_doc.filename}] {request.query[:50]}"
        convo = crud.create_conversation(db, schemas.ConversationCreate(title=title))

    # Save user message
    crud.create_message(db, schemas.MessageCreate(
        conversation_id=convo.id, role="user", content=request.query,
    ))

    # Retrieve relevant chunks via semantic search
    try:
        relevant_chunks = file_service.retrieve_chunks(
            query=request.query,
            file_id=request.file_id,
            db=db,
        )
    except Exception as e:
        logger.error("Chunk retrieval failed for file_id=%s: %s", request.file_id, e)
        relevant_chunks = []

    if not relevant_chunks:
        no_context_reply = "I couldn't find relevant information in the document to answer your question."
        assistant_msg = crud.create_message(db, schemas.MessageCreate(
            conversation_id=convo.id, role="assistant", content=no_context_reply,
        ))
        return schemas.ChatResponse(
            reply=no_context_reply,
            conversation_id=convo.id,
            message_id=assistant_msg.id,
            model=ai_service.MODEL_NAME,
        )

    # Format document context block
    context_block = "\n\n---\n\n".join(
        f"[Excerpt {i+1}]\n{chunk}" for i, chunk in enumerate(relevant_chunks)
    )
    context_message = {
        "role": "user",
        "content": f"Document context (use ONLY this to answer):\n\n{context_block}",
    }

    # Build conversation history (last 10 turns max)
    existing = crud.get_messages(db, convo.id)
    history  = [{"role": m.role, "content": m.content} for m in existing[:-1]]
    if len(history) > 10:
        history = history[-10:]

    # Call Groq with document-specific system prompt
    reply = ai_service.generate_response(
        message=request.query,
        history=[context_message] + history,
        system_prompt_override=FILE_CHAT_SYSTEM_PROMPT,
    )

    # Persist assistant reply
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
    """Delete a file document and all its chunks. Evicts in-memory FAISS index."""
    deleted = crud.delete_file_document(db, file_id)
    file_service.evict_index(file_id)
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
