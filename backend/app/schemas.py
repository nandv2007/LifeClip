"""Pydantic request/response schemas — the API contract."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

CATEGORIES = (
    "event", "receipt", "ticket", "notes", "menu", "product", "document", "other",
)


# ---------- Health ----------
class HealthOut(BaseModel):
    status: str
    version: str
    database: str  # "ok" | "error"
    cloudinary_configured: bool
    time: datetime


# ---------- Upload signing ----------
class UploadSignatureIn(BaseModel):
    filename: str = Field(min_length=1, max_length=255)
    mime_type: str = Field(min_length=3, max_length=64)
    byte_size: int = Field(gt=0)


class UploadSignatureOut(BaseModel):
    upload_url: str
    cloud_name: str
    api_key: str
    timestamp: int
    folder: str
    public_id: str
    signature: str
    tags: str
    context: str
    max_upload_bytes: int


# ---------- Clips ----------
class ClipCreateIn(BaseModel):
    """Sent by the browser AFTER the direct-to-Cloudinary upload succeeds.
    The server re-verifies the asset with the Admin API instead of trusting
    these client-provided values."""

    public_id: str = Field(min_length=1, max_length=255)
    original_filename: str = Field(default="", max_length=255)
    mime_type: str = Field(default="image/jpeg", max_length=64)


class FieldOut(BaseModel):
    id: str
    name: str
    label: str
    value: str
    confidence: float
    user_edited: bool


class ActionOut(BaseModel):
    id: str
    action_type: str
    label: str
    reason: str
    primary: bool
    status: str
    payload: dict[str, Any]


class ClipListItem(BaseModel):
    id: str
    status: str
    category: str | None
    title: str | None
    thumbnail_url: str
    preview_url: str
    created_at: datetime


class ClipDetail(BaseModel):
    id: str
    status: str
    category: str | None
    title: str | None
    original_filename: str
    mime_type: str
    byte_size: int
    width: int
    height: int
    secure_url: str
    preview_url: str
    thumbnail_url: str
    raw_text: str | None
    analysis_error: str | None
    fields: list[FieldOut]
    actions: list[ActionOut]
    created_at: datetime
    updated_at: datetime


class ClipPatchIn(BaseModel):
    title: str | None = Field(default=None, max_length=255)
    category: str | None = None

    @field_validator("category")
    @classmethod
    def _valid_category(cls, v):
        if v is not None and v not in CATEGORIES:
            raise ValueError(f"category must be one of {CATEGORIES}")
        return v


class FieldPatchItem(BaseModel):
    id: str | None = None  # existing field id; None = create new
    name: str = Field(min_length=1, max_length=64)
    label: str = Field(default="", max_length=128)
    value: str = Field(default="", max_length=2000)


class FieldsPatchIn(BaseModel):
    fields: list[FieldPatchItem] = Field(min_length=1, max_length=60)


# ---------- Analysis ----------
class AnalyzeIn(BaseModel):
    force: bool = False


class AnalysisStatusOut(BaseModel):
    clip_id: str
    status: str          # clip-level status
    run_id: str | None
    run_status: str | None
    phase: str | None
    phase_message: str | None
    error: str | None


# ---------- Actions ----------
class ActionConfirmIn(BaseModel):
    """Edited, user-approved payload for a consequential action (e.g. an
    edited calendar event). The server re-validates before accepting."""
    payload: dict[str, Any] = Field(default_factory=dict)


class ActionConfirmOut(BaseModel):
    id: str
    status: str
    # For calendar/reminder the server produces a downloadable .ics file:
    download_url: str | None = None
    # For actions that produce text content (summary/copy):
    content: str | None = None
    # For actions that open an external site (maps/search/translate):
    external_url: str | None = None


class StudyIn(BaseModel):
    mode: Literal["summary", "explain", "quiz", "flashcards"]


class StudyOut(BaseModel):
    mode: str
    items: list[dict[str, Any]]


# ---------- Settings ----------
class SettingsOut(BaseModel):
    retention_days: int
    save_extracted_text: bool


class SettingsPatchIn(BaseModel):
    retention_days: int | None = Field(default=None, ge=0, le=3650)
    save_extracted_text: bool | None = None
