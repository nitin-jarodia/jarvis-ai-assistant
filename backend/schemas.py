"""
Pydantic schemas for request/response validation in Jarvis AI Assistant.
"""

from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional


# ─── Conversation Schemas ─────────────────────────────────────────────────────

class ConversationCreate(BaseModel):
    title: str = Field(default="New Conversation", max_length=255)
    document_file_id: Optional[str] = None
    document_filename: Optional[str] = Field(default=None, max_length=255)


class ConversationUpdate(BaseModel):
    title: Optional[str] = Field(None, max_length=255)
    document_file_id: Optional[str] = None
    document_filename: Optional[str] = Field(default=None, max_length=255)
    is_active: Optional[bool] = None


class ConversationOut(BaseModel):
    id: int
    title: str
    document_file_id: Optional[str]
    document_filename: Optional[str]
    created_at: datetime
    updated_at: Optional[datetime]
    is_active: bool

    model_config = {"from_attributes": True}


# ─── Message Schemas ──────────────────────────────────────────────────────────

class MessageCreate(BaseModel):
    conversation_id: int
    role: str = Field(..., pattern="^(user|assistant)$")
    content: str = Field(..., min_length=1)


class MessageOut(BaseModel):
    id: int
    conversation_id: int
    role: str
    content: str
    created_at: datetime

    model_config = {"from_attributes": True}


# ─── Chat Request / Response ──────────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, description="User message to Jarvis")
    conversation_id: Optional[int] = None


class ChatResponse(BaseModel):
    reply: str
    conversation_id: int
    message_id: int
    model: Optional[str] = None


# ─── Note Schemas ─────────────────────────────────────────────────────────────

class NoteCreate(BaseModel):
    title: str = Field(..., max_length=255)
    content: str = Field(..., min_length=1)


class NoteUpdate(BaseModel):
    title: Optional[str] = Field(None, max_length=255)
    content: Optional[str] = None


class NoteOut(BaseModel):
    id: int
    title: str
    content: str
    created_at: datetime
    updated_at: Optional[datetime]

    model_config = {"from_attributes": True}


# ─── File / Document Schemas ──────────────────────────────────────────────────

class UploadResponse(BaseModel):
    file_id: str
    filename: str
    file_type: str
    chunk_count: int


class FileChatRequest(BaseModel):
    query: str = Field(..., min_length=1, description="User question about the document")
    file_id: str = Field(..., description="UUID of the uploaded file")
    conversation_id: Optional[int] = None


class FileDocumentOut(BaseModel):
    file_id: str
    filename: str
    file_type: str
    chunk_count: int
    created_at: datetime

    model_config = {"from_attributes": True}
