"""
Database configuration and session management for Jarvis AI Assistant.
Uses SQLite via SQLAlchemy 2.x.
"""

import os
import logging
from sqlalchemy import create_engine
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


class Base(DeclarativeBase):
    """SQLAlchemy 2.x declarative base."""
    pass


def get_db():
    """FastAPI dependency: provides a DB session per request, auto-closes after."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Create all tables in the database on startup."""
    from backend import models  # noqa: F401 - import triggers model registration
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables created/verified at: %s", DATABASE_URL)
