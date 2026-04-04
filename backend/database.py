"""
Database configuration and session management for Jarvis AI Assistant.
Uses SQLite via SQLAlchemy 2.x.
"""

import os
import logging
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker, DeclarativeBase

logger = logging.getLogger(__name__)

# SQLite database file stored in project root
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATABASE_URL = f"sqlite:///{os.path.join(BASE_DIR, 'jarvis.db')}"

logger.debug("Using database: %s", DATABASE_URL)

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},  # Required for SQLite with FastAPI
    echo=False,  # Set to True to log all SQL statements
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
_db_ready = False


class Base(DeclarativeBase):
    """SQLAlchemy 2.x declarative base."""
    pass


def get_db():
    """FastAPI dependency: provides a DB session per request, auto-closes after."""
    ensure_db_ready()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Create all tables in the database on startup."""
    ensure_db_ready()
    logger.info("Database tables created/verified at: %s", DATABASE_URL)


def ensure_db_ready():
    """Initialize tables and apply migrations once per process."""
    global _db_ready
    if _db_ready:
        return

    from backend import models  # noqa: F401 - import triggers model registration

    Base.metadata.create_all(bind=engine)
    _run_migrations()
    _db_ready = True


def _run_migrations():
    """Apply lightweight SQLite schema migrations for newly added columns."""
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
