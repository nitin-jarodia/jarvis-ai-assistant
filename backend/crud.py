"""CRUD (Create, Read, Update, Delete) operations for Jarvis AI Assistant."""
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from backend import models, schemas


def _utc_now():
    return datetime.now(timezone.utc)


def get_user_chats(db: Session, user_id: int, skip: int = 0, limit: int = 50):
    return (
        db.query(models.Chat)
        .filter(models.Chat.user_id == user_id, models.Chat.is_active.is_(True))
        .order_by(models.Chat.updated_at.desc(), models.Chat.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )


def get_user_chat(db: Session, chat_id: int, user_id: int):
    return (
        db.query(models.Chat)
        .filter(
            models.Chat.id == chat_id,
            models.Chat.user_id == user_id,
            models.Chat.is_active.is_(True),
        )
        .first()
    )


def create_chat(db: Session, user_id: int, data: schemas.ChatCreateRequest):
    chat = models.Chat(user_id=user_id, title=data.title, updated_at=_utc_now())
    db.add(chat)
    db.commit()
    db.refresh(chat)
    return chat


def update_chat(db: Session, chat: models.Chat, data: schemas.ChatUpdate):
    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(chat, key, value)
    chat.updated_at = _utc_now()
    db.commit()
    db.refresh(chat)
    return chat


def touch_chat(db: Session, chat: models.Chat):
    chat.updated_at = _utc_now()
    db.commit()
    db.refresh(chat)
    return chat


def delete_chat(db: Session, chat: models.Chat):
    db.query(models.Message).filter(models.Message.chat_id == chat.id).delete()
    db.delete(chat)
    db.commit()


def get_chat_messages(db: Session, chat_id: int):
    return (
        db.query(models.Message)
        .filter(models.Message.chat_id == chat_id)
        .order_by(models.Message.created_at.asc(), models.Message.id.asc())
        .all()
    )


def create_message(db: Session, data: schemas.MessageCreate):
    message = models.Message(
        conversation_id=data.chat_id,
        chat_id=data.chat_id,
        role=data.role,
        agent_type=data.agent_type,
        content=data.content,
        message_type=data.message_type,
        image_url=data.image_url,
        attachment_url=data.attachment_url,
        provider=data.provider,
        response_type=data.response_type,
        metadata_json=data.metadata_json,
    )
    db.add(message)
    db.commit()
    db.refresh(message)
    return message


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
    obj.updated_at = _utc_now()
    db.commit()
    db.refresh(obj)
    return obj


def delete_note(db: Session, note_id: int):
    obj = get_note(db, note_id)
    if obj:
        db.delete(obj)
        db.commit()
    return obj


def create_file_document(
    db: Session,
    *,
    user_id: int,
    file_id: str,
    filename: str,
    file_type: str,
    chunk_count: int,
):
    file_doc = models.FileDocument(
        user_id=user_id,
        file_id=file_id,
        filename=filename,
        file_type=file_type,
        chunk_count=chunk_count,
    )
    db.add(file_doc)
    db.commit()
    db.refresh(file_doc)
    return file_doc


def get_user_file_document(db: Session, file_id: str, user_id: int):
    return (
        db.query(models.FileDocument)
        .filter(models.FileDocument.file_id == file_id, models.FileDocument.user_id == user_id)
        .first()
    )


def get_user_file_documents(db: Session, user_id: int, skip: int = 0, limit: int = 50):
    return (
        db.query(models.FileDocument)
        .filter(models.FileDocument.user_id == user_id)
        .order_by(models.FileDocument.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )


def delete_user_file_document(db: Session, file_id: str, user_id: int) -> bool:
    db.query(models.FileChunk).filter(models.FileChunk.file_id == file_id).delete()
    deleted = (
        db.query(models.FileDocument)
        .filter(models.FileDocument.file_id == file_id, models.FileDocument.user_id == user_id)
        .delete()
    )
    db.commit()
    return deleted > 0


def create_file_chunks(db: Session, file_id: str, chunks: list[tuple[int, str, bytes]]) -> None:
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
