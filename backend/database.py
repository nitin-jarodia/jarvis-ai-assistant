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

    if "conversations" not in table_names:
        return

    conversation_columns = {
        column["name"] for column in inspector.get_columns("conversations")
    }
    statements: list[str] = []

    if "document_file_id" not in conversation_columns:
        statements.append(
            "ALTER TABLE conversations ADD COLUMN document_file_id VARCHAR(36)"
        )
    if "document_filename" not in conversation_columns:
        statements.append(
            "ALTER TABLE conversations ADD COLUMN document_filename VARCHAR(255)"
        )

    if not statements:
        return

    with engine.begin() as connection:
        for statement in statements:
            connection.execute(text(statement))
