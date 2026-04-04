"""
SQLAlchemy ORM models for Jarvis AI Assistant.
"""

from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, LargeBinary
from sqlalchemy.sql import func
from backend.database import Base


class Conversation(Base):
    """Stores chat conversation sessions."""
    __tablename__ = "conversations"

    id                = Column(Integer, primary_key=True, index=True)
    title             = Column(String(255), nullable=False, default="New Conversation")
    document_file_id  = Column(String(36), nullable=True, index=True)
    document_filename = Column(String(255), nullable=True)
    created_at        = Column(DateTime(timezone=True), server_default=func.now())
    updated_at        = Column(DateTime(timezone=True), onupdate=func.now())
    is_active         = Column(Boolean, default=True)


class Message(Base):
    """Stores individual messages within a conversation."""
    __tablename__ = "messages"

    id              = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(Integer, nullable=False, index=True)
    role            = Column(String(50), nullable=False)   # 'user' or 'assistant'
    content         = Column(Text, nullable=False)
    created_at      = Column(DateTime(timezone=True), server_default=func.now())


class Note(Base):
    """Stores quick notes saved by the user via Jarvis."""
    __tablename__ = "notes"

    id         = Column(Integer, primary_key=True, index=True)
    title      = Column(String(255), nullable=False)
    content    = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


# ─── Document / File Models ───────────────────────────────────────────────────

class FileDocument(Base):
    """Metadata for an uploaded file document."""
    __tablename__ = "file_documents"

    id          = Column(Integer, primary_key=True, index=True)
    file_id     = Column(String(36), unique=True, index=True, nullable=False)  # UUID
    filename    = Column(String(255), nullable=False)
    file_type   = Column(String(10), nullable=False)   # 'pdf' or 'txt'
    chunk_count = Column(Integer, nullable=False, default=0)
    created_at  = Column(DateTime(timezone=True), server_default=func.now())


class FileChunk(Base):
    """A single text chunk from a FileDocument with its embedding vector."""
    __tablename__ = "file_chunks"

    id          = Column(Integer, primary_key=True, index=True)
    file_id     = Column(String(36), nullable=False, index=True)
    chunk_index = Column(Integer, nullable=False)     # order within document
    content     = Column(Text, nullable=False)
    embedding   = Column(LargeBinary, nullable=False) # float32 bytes
