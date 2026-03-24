"""
Jarvis AI Assistant — FastAPI main application.
Run with: uvicorn backend.main:app --reload
"""

import os
import logging
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import List

from backend.database import get_db, init_db
from backend import crud, schemas
from backend import ai_service

# ─── Logging Setup ────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# ─── App Initialization ───────────────────────────────────────────────────────

app = FastAPI(
    title="Jarvis AI Assistant",
    description="A personal AI assistant backend powered by FastAPI and SQLite.",
    version="1.0.0",
)

# Serve the frontend static files
FRONTEND_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")
STATIC_DIR = os.path.join(FRONTEND_DIR, "static")

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup():
    """Initialize database tables on startup."""
    init_db()
    logger.info("=== Jarvis AI Assistant started ===")
    ai_info = ai_service.check_ai_service()
    if ai_info["status"] == "ok":
        logger.info("AI Service: Ready | model '%s'", ai_service.MODEL_NAME)
    else:
        logger.warning("AI Service Error: %s", ai_info.get("detail", "Unknown"))


# ─── Root Route (Serves Frontend) ────────────────────────────────────────────

@app.get("/", include_in_schema=False)
def serve_frontend():
    """Serve the main HTML frontend."""
    return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))


# ─── Health Check ─────────────────────────────────────────────────────────────

@app.get("/api/health", tags=["Health"])
def health_check():
    """Check if the API is running and report AI service status."""
    ai_status = ai_service.check_ai_service()
    return {
        "status": "ok",
        "service": "Jarvis AI Assistant",
        "ai_service": ai_status,
    }


# ─── Chat Endpoint ────────────────────────────────────────────────────────────

@app.post("/api/chat", response_model=schemas.ChatResponse, tags=["Chat"])
def chat(request: schemas.ChatRequest, db: Session = Depends(get_db)):
    """
    Send a message to Jarvis (powered by Groq).
    Passes full conversation history for context-aware replies.
    """
    logger.info("POST /api/chat | conv_id=%s | msg='%.60s'...", request.conversation_id, request.message)

    # Get or create conversation
    if request.conversation_id:
        convo = crud.get_conversation(db, request.conversation_id)
        if not convo:
            raise HTTPException(status_code=404, detail="Conversation not found.")
    else:
        convo = crud.create_conversation(
            db, schemas.ConversationCreate(title=request.message[:60])
        )
        logger.debug("Created conversation id=%d", convo.id)

    # Save user message first
    crud.create_message(db, schemas.MessageCreate(
        conversation_id=convo.id,
        role="user",
        content=request.message,
    ))

    # Build history (all messages except the one we just saved)
    existing = crud.get_messages(db, convo.id)
    history = [
        {"role": m.role, "content": m.content}
        for m in existing[:-1]
    ]
    
    # Limit history to last 15 messages for context window stability
    if len(history) > 15:
        history = history[-15:]

    # Call AI Service
    reply = ai_service.generate_response(request.message, history=history)

    # Persist assistant reply
    assistant_msg = crud.create_message(db, schemas.MessageCreate(
        conversation_id=convo.id,
        role="assistant",
        content=reply,
    ))

    logger.info("✓ Chat response | conv_id=%d | reply_len=%d", convo.id, len(reply))

    return schemas.ChatResponse(
        reply=reply,
        conversation_id=convo.id,
        message_id=assistant_msg.id,
        model=ai_service.MODEL_NAME,
    )



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
