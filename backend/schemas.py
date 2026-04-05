"""Pydantic schemas for request/response validation in Jarvis AI Assistant."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field


class UserRegister(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)


class UserLogin(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)


class RegisterResponse(BaseModel):
    message: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class ProtectedResponse(BaseModel):
    user_id: int


class ChatCreateRequest(BaseModel):
    title: str = Field(default="New Chat", max_length=255)


class ChatUpdate(BaseModel):
    title: Optional[str] = Field(default=None, max_length=255)
    document_file_id: Optional[str] = None
    document_filename: Optional[str] = Field(default=None, max_length=255)
    is_active: Optional[bool] = None


class ChatOut(BaseModel):
    id: int
    user_id: Optional[int]
    title: str
    document_file_id: Optional[str]
    document_filename: Optional[str]
    created_at: datetime
    updated_at: Optional[datetime]
    is_active: bool

    model_config = {"from_attributes": True}


class MessageCreate(BaseModel):
    chat_id: int
    role: str = Field(..., pattern="^(user|assistant)$")
    agent_type: Optional[str] = Field(default=None, pattern="^(coding|research|planning|debugging)?$")
    content: str = Field(..., min_length=1)


class MessageOut(BaseModel):
    id: int
    chat_id: int
    role: str
    agent_type: Optional[str] = None
    content: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ChatMessageRequest(BaseModel):
    content: str = Field(..., min_length=1, description="User message to Jarvis")
    file_id: Optional[str] = None


class ChatMessageResponse(BaseModel):
    reply: str
    chat_id: int
    user_message_id: int
    assistant_message_id: int
    agent_type: Optional[str] = None
    model: Optional[str] = None


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, description="User message to Jarvis")
    conversation_id: Optional[int] = None


class ChatResponse(BaseModel):
    reply: str
    conversation_id: int
    message_id: int
    agent_type: Optional[str] = None
    model: Optional[str] = None


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
    user_id: Optional[int]
    filename: str
    file_type: str
    chunk_count: int
    created_at: datetime

    model_config = {"from_attributes": True}
