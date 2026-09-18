"""Relational data model.

sessions ─┬─ clips ─┬─ extracted_fields
          │         ├─ analysis_runs
          │         └─ actions
          └─ session_settings
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Session(Base):
    """Anonymous device session — LifeClip works without an account.

    The frontend generates a random token once, stores it in localStorage and
    sends it on every request. Deleting the session deletes everything it owns.
    """

    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    clips: Mapped[list["Clip"]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )
    settings: Mapped["SessionSettings"] = relationship(
        back_populates="session", cascade="all, delete-orphan", uselist=False
    )


class SessionSettings(Base):
    __tablename__ = "session_settings"

    session_id: Mapped[str] = mapped_column(
        ForeignKey("sessions.id", ondelete="CASCADE"), primary_key=True
    )
    retention_days: Mapped[int] = mapped_column(Integer, default=90)  # 0 = keep forever
    save_extracted_text: Mapped[bool] = mapped_column(Boolean, default=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    session: Mapped[Session] = relationship(back_populates="settings")


class Clip(Base):
    __tablename__ = "clips"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    session_id: Mapped[str] = mapped_column(
        ForeignKey("sessions.id", ondelete="CASCADE"), index=True
    )

    # --- Cloudinary asset reference ---
    cloudinary_public_id: Mapped[str] = mapped_column(String(255), unique=True)
    cloudinary_resource_type: Mapped[str] = mapped_column(String(16), default="image")
    secure_url: Mapped[str] = mapped_column(Text)
    format: Mapped[str] = mapped_column(String(16), default="jpg")
    width: Mapped[int] = mapped_column(Integer, default=0)
    height: Mapped[int] = mapped_column(Integer, default=0)
    byte_size: Mapped[int] = mapped_column(Integer, default=0)
    original_filename: Mapped[str] = mapped_column(String(255), default="")
    mime_type: Mapped[str] = mapped_column(String(64), default="image/jpeg")

    # --- Status lifecycle: uploaded -> queued -> analyzing -> ready|partial|failed ---
    status: Mapped[str] = mapped_column(String(24), default="uploaded", index=True)

    # --- Analysis outcome ---
    category: Mapped[str | None] = mapped_column(String(24), nullable=True)
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    raw_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    analysis_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    session: Mapped[Session] = relationship(back_populates="clips")
    fields: Mapped[list["ExtractedField"]] = relationship(
        back_populates="clip", cascade="all, delete-orphan", order_by="ExtractedField.position"
    )
    actions: Mapped[list["Action"]] = relationship(
        back_populates="clip", cascade="all, delete-orphan", order_by="Action.position"
    )
    runs: Mapped[list["AnalysisRun"]] = relationship(
        back_populates="clip", cascade="all, delete-orphan", order_by="AnalysisRun.created_at"
    )

    __table_args__ = (Index("ix_clips_session_created", "session_id", "created_at"),)


class ExtractedField(Base):
    __tablename__ = "extracted_fields"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    clip_id: Mapped[str] = mapped_column(
        ForeignKey("clips.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(64))
    label: Mapped[str] = mapped_column(String(128), default="")
    value: Mapped[str] = mapped_column(Text, default="")
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    position: Mapped[int] = mapped_column(Integer, default=0)
    user_edited: Mapped[bool] = mapped_column(Boolean, default=False)

    clip: Mapped[Clip] = relationship(back_populates="fields")


class Action(Base):
    __tablename__ = "actions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    clip_id: Mapped[str] = mapped_column(
        ForeignKey("clips.id", ondelete="CASCADE"), index=True
    )
    action_type: Mapped[str] = mapped_column(String(32))  # calendar, reminder, ...
    label: Mapped[str] = mapped_column(String(128))
    reason: Mapped[str] = mapped_column(String(255), default="")  # why suggested
    primary: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(24), default="suggested")  # suggested|confirmed|done|dismissed
    payload: Mapped[str] = mapped_column(Text, default="{}")  # JSON metadata
    position: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    clip: Mapped[Clip] = relationship(back_populates="actions")


class AnalysisRun(Base):
    """One row per analysis attempt — makes analysis idempotent and auditable."""

    __tablename__ = "analysis_runs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    clip_id: Mapped[str] = mapped_column(
        ForeignKey("clips.id", ondelete="CASCADE"), index=True
    )
    attempt: Mapped[int] = mapped_column(Integer, default=1)
    # queued -> running -> succeeded | failed | partial
    status: Mapped[str] = mapped_column(String(24), default="queued")
    phase: Mapped[str] = mapped_column(String(64), default="queued")  # truthful progress phase
    provider: Mapped[str] = mapped_column(String(64), default="local-ocr-rules/v1")
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    clip: Mapped[Clip] = relationship(back_populates="runs")
