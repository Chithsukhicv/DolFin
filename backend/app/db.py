"""SQLAlchemy setup. SQLite for dev; pluggable later."""

from __future__ import annotations

from pathlib import Path
from typing import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings


class Base(DeclarativeBase):
    pass


_settings = get_settings()
_db_file = (_settings.project_root / "data" / "dolfin.db").resolve()
_db_file.parent.mkdir(parents=True, exist_ok=True)

engine = create_engine(
    f"sqlite:///{_db_file}",
    connect_args={"check_same_thread": False},
    future=True,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def get_db() -> Iterator[Session]:
    """FastAPI dependency that yields a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_models() -> None:
    """Import all model modules so SQLAlchemy registers them, then create tables."""
    # Importing here avoids circular imports at module load time.
    from app import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
