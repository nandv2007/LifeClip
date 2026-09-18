"""Database engine + session management."""

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import get_settings


class Base(DeclarativeBase):
    pass


def _make_engine():
    url = get_settings().resolved_database_url
    connect_args = {}
    if url.startswith("sqlite"):
        connect_args["check_same_thread"] = False
    engine = create_engine(url, pool_pre_ping=True, connect_args=connect_args)
    if url.startswith("sqlite"):
        # Reasonable durability/concurrency defaults for a local SQLite file.
        @event.listens_for(engine, "connect")
        def _sqlite_pragma(dbapi_connection, _):  # pragma: no cover - trivial
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()
    return engine


engine = _make_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def init_db() -> None:
    """Create tables (idempotent). For larger deployments use Alembic; for
    the MVP create_all is sufficient and keeps setup one-command simple."""
    from . import models  # noqa: F401  (ensure models are imported)

    Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
