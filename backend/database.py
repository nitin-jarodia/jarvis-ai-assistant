"""Database configuration and session management for Jarvis AI Assistant."""

import logging
import os
from typing import Generator

from dotenv import load_dotenv
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

load_dotenv()

logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATABASE_URL = f"sqlite:///{os.path.join(BASE_DIR, 'jarvis.db')}"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
    echo=False,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
_db_ready = False


class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session, None, None]:
    ensure_db_ready()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    ensure_db_ready()
    logger.info("Database tables created/verified at: %s", DATABASE_URL)


def ensure_db_ready() -> None:
    global _db_ready
    if _db_ready:
        return

    from backend import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    _run_migrations()
    _db_ready = True


def _run_migrations() -> None:
    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())
    with engine.begin() as connection:
        if "users" in table_names:
            user_columns = {column["name"] for column in inspector.get_columns("users")}
            if "password_hash" not in user_columns:
                connection.execute(text("ALTER TABLE users ADD COLUMN password_hash VARCHAR(255)"))
            if "password" in user_columns:
                connection.execute(
                    text(
                        "UPDATE users SET password_hash = password "
                        "WHERE password_hash IS NULL OR password_hash = ''"
                    )
                )

        if "conversations" in table_names:
            conversation_columns = {
                column["name"] for column in inspector.get_columns("conversations")
            }
            if "document_file_id" not in conversation_columns:
                connection.execute(
                    text("ALTER TABLE conversations ADD COLUMN document_file_id VARCHAR(36)")
                )
            if "document_filename" not in conversation_columns:
                connection.execute(
                    text("ALTER TABLE conversations ADD COLUMN document_filename VARCHAR(255)")
                )

        if "messages" in table_names:
            message_columns = {column["name"] for column in inspector.get_columns("messages")}
            if "chat_id" not in message_columns:
                connection.execute(text("ALTER TABLE messages ADD COLUMN chat_id INTEGER"))
                if "conversation_id" in message_columns:
                    connection.execute(text("UPDATE messages SET chat_id = conversation_id WHERE chat_id IS NULL"))
            if "agent_type" not in message_columns:
                connection.execute(text("ALTER TABLE messages ADD COLUMN agent_type VARCHAR(32)"))
            if "message_type" not in message_columns:
                connection.execute(text("ALTER TABLE messages ADD COLUMN message_type VARCHAR(32)"))
                connection.execute(text("UPDATE messages SET message_type = 'text' WHERE message_type IS NULL"))
            if "image_url" not in message_columns:
                connection.execute(text("ALTER TABLE messages ADD COLUMN image_url VARCHAR(1024)"))
            if "attachment_url" not in message_columns:
                connection.execute(text("ALTER TABLE messages ADD COLUMN attachment_url VARCHAR(1024)"))
            if "provider" not in message_columns:
                connection.execute(text("ALTER TABLE messages ADD COLUMN provider VARCHAR(64)"))
            if "response_type" not in message_columns:
                connection.execute(text("ALTER TABLE messages ADD COLUMN response_type VARCHAR(32)"))
            if "metadata_json" not in message_columns:
                connection.execute(text("ALTER TABLE messages ADD COLUMN metadata_json TEXT"))
            connection.execute(text("CREATE INDEX IF NOT EXISTS ix_messages_chat_id ON messages (chat_id)"))

        if "file_documents" in table_names:
            file_columns = {column["name"] for column in inspector.get_columns("file_documents")}
            if "user_id" not in file_columns:
                connection.execute(text("ALTER TABLE file_documents ADD COLUMN user_id INTEGER"))
            connection.execute(text("CREATE INDEX IF NOT EXISTS ix_file_documents_user_id ON file_documents (user_id)"))

        if "chats" in table_names and "conversations" in table_names:
            chat_count = connection.execute(text("SELECT COUNT(*) FROM chats")).scalar_one()
            if chat_count == 0:
                connection.execute(
                    text(
                        """
                        INSERT INTO chats (
                            id, user_id, title, document_file_id, document_filename,
                            created_at, updated_at, is_active
                        )
                        SELECT
                            id,
                            NULL,
                            COALESCE(title, 'New Chat'),
                            document_file_id,
                            document_filename,
                            created_at,
                            updated_at,
                            COALESCE(is_active, 1)
                        FROM conversations
                        """
                    )
                )

        if "messages" in table_names:
            connection.execute(
                text(
                    "UPDATE messages SET chat_id = conversation_id "
                    "WHERE chat_id IS NULL AND conversation_id IS NOT NULL"
                )
            )
