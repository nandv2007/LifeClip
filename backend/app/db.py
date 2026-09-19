"""Database engine + session management."""

from sqlalchemy import create_engine, event, inspect, text
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


def _migrate_clip_columns() -> None:
    """Small additive migration for existing LifeClip installations.

    We never replace the existing database. These nullable/defaulted columns
    are safe on SQLite and PostgreSQL and leave old clips fully readable.
    """
    existing = {column["name"] for column in inspect(engine).get_columns("clips")}
    additions = {
        "subject": "VARCHAR(120)",
        "topic": "VARCHAR(200)",
        "tags_json": "TEXT NOT NULL DEFAULT '[]'",
        "headings_json": "TEXT NOT NULL DEFAULT '[]'",
        "concepts_json": "TEXT NOT NULL DEFAULT '[]'",
        "extracted_text_status": "VARCHAR(32)",
        "ocr_used": "BOOLEAN NOT NULL DEFAULT TRUE",
        "analysis_confidence": "FLOAT",
        "analysis_warnings_json": "TEXT NOT NULL DEFAULT '[]'",
    }
    with engine.begin() as connection:
        for name, ddl in additions.items():
            if name not in existing:
                connection.execute(text(f"ALTER TABLE clips ADD COLUMN {name} {ddl}"))


def _migrate_session_columns() -> None:
    """Attach existing anonymous sessions to accounts without replacing them."""
    existing = {column["name"] for column in inspect(engine).get_columns("sessions")}
    with engine.begin() as connection:
        if "user_id" not in existing:
            # Existing installations retain every session and clip. Fresh
            # databases receive the full FK through SQLAlchemy create_all.
            connection.execute(text("ALTER TABLE sessions ADD COLUMN user_id VARCHAR(64)"))
        connection.execute(
            text("CREATE UNIQUE INDEX IF NOT EXISTS ix_sessions_user_id ON sessions (user_id)")
        )


def init_db() -> None:
    """Create tables and apply backward-compatible additive migrations."""
    from . import models  # noqa: F401  (ensure models are imported)

    Base.metadata.create_all(bind=engine)
    _migrate_session_columns()
    _migrate_clip_columns()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
