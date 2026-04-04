"""
CRUD (Create, Read, Update, Delete) operations for Jarvis AI Assistant.
"""

from sqlalchemy.orm import Session
from datetime import datetime, timezone
from backend import models, schemas


# ─── Conversation CRUD ────────────────────────────────────────────────────────

def get_conversations(db: Session, skip: int = 0, limit: int = 50):
    return (
        db.query(models.Conversation)
        .filter(models.Conversation.is_active == True)
        .order_by(models.Conversation.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )


def get_conversation(db: Session, conversation_id: int):
    return db.query(models.Conversation).filter(models.Conversation.id == conversation_id).first()


def create_conversation(db: Session, data: schemas.ConversationCreate):
    obj = models.Conversation(
        title=data.title,
        document_file_id=data.document_file_id,
        document_filename=data.document_filename,
    )
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


def update_conversation(db: Session, conversation_id: int, data: schemas.ConversationUpdate):
    obj = get_conversation(db, conversation_id)
    if not obj:
        return None
    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(obj, key, value)
    obj.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(obj)
    return obj


def delete_conversation(db: Session, conversation_id: int):
    obj = get_conversation(db, conversation_id)
    if obj:
        obj.is_active = False
        db.commit()
    return obj


# ─── Message CRUD ─────────────────────────────────────────────────────────────

def get_messages(db: Session, conversation_id: int):
    return (
        db.query(models.Message)
        .filter(models.Message.conversation_id == conversation_id)
        .order_by(models.Message.created_at.asc())
        .all()
    )


def create_message(db: Session, data: schemas.MessageCreate):
    obj = models.Message(
        conversation_id=data.conversation_id,
        role=data.role,
        content=data.content,
    )
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


# ─── Note CRUD ────────────────────────────────────────────────────────────────

def get_notes(db: Session, skip: int = 0, limit: int = 100):
    return (
        db.query(models.Note)
        .order_by(models.Note.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )


def get_note(db: Session, note_id: int):
    return db.query(models.Note).filter(models.Note.id == note_id).first()


def create_note(db: Session, data: schemas.NoteCreate):
    obj = models.Note(title=data.title, content=data.content)
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


def update_note(db: Session, note_id: int, data: schemas.NoteUpdate):
    obj = get_note(db, note_id)
    if not obj:
        return None
    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(obj, key, value)
    obj.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(obj)
    return obj


def delete_note(db: Session, note_id: int):
    obj = get_note(db, note_id)
    if obj:
        db.delete(obj)
        db.commit()
    return obj


# ─── File Document CRUD ───────────────────────────────────────────────────────

def create_file_document(db: Session, file_id: str, filename: str, file_type: str, chunk_count: int):
    obj = models.FileDocument(
        file_id=file_id,
        filename=filename,
        file_type=file_type,
        chunk_count=chunk_count,
    )
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


def get_file_document(db: Session, file_id: str):
    return db.query(models.FileDocument).filter(models.FileDocument.file_id == file_id).first()


def get_file_documents(db: Session, skip: int = 0, limit: int = 50):
    return (
        db.query(models.FileDocument)
        .order_by(models.FileDocument.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )


def delete_file_document(db: Session, file_id: str) -> bool:
    """Delete the document record and all its associated chunks."""
    # Delete chunks first
    db.query(models.FileChunk).filter(models.FileChunk.file_id == file_id).delete()
    # Delete document record
    deleted = db.query(models.FileDocument).filter(models.FileDocument.file_id == file_id).delete()
    db.commit()
    return deleted > 0


# ─── File Chunk CRUD ──────────────────────────────────────────────────────────

def create_file_chunks(db: Session, file_id: str, chunks: list[tuple[int, str, bytes]]) -> None:
    """
    Bulk-insert file chunks.
    chunks: list of (chunk_index, content, embedding_bytes)
    """
    objects = [
        models.FileChunk(
            file_id=file_id,
            chunk_index=idx,
            content=text,
            embedding=emb_bytes or b"",
        )
        for idx, text, emb_bytes in chunks
    ]
    db.bulk_save_objects(objects)
    db.commit()


def get_file_chunks(db: Session, file_id: str) -> list[models.FileChunk]:
    return (
        db.query(models.FileChunk)
        .filter(models.FileChunk.file_id == file_id)
        .order_by(models.FileChunk.chunk_index.asc())
        .all()
    )
