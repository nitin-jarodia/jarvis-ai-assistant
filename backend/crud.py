"""
CRUD (Create, Read, Update, Delete) operations for Jarvis AI Assistant.
"""

from sqlalchemy.orm import Session
from datetime import datetime
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
    obj = models.Conversation(title=data.title)
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
    obj.updated_at = datetime.utcnow()
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
    obj.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(obj)
    return obj


def delete_note(db: Session, note_id: int):
    obj = get_note(db, note_id)
    if obj:
        db.delete(obj)
        db.commit()
    return obj
