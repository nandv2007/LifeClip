"""Pydantic request/response schemas — the LifeClip API contract."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, EmailStr, Field, field_validator

CATEGORIES = (
    "event", "receipt", "ticket", "notes", "menu", "product", "document", "other",
)


class HealthOut(BaseModel):
    status: str
    version: str
    database: str
    cloudinary_configured: bool
    time: datetime


class SignUpIn(BaseModel):
    username: str = Field(min_length=3, max_length=30)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)

    @field_validator("username")
    @classmethod
    def _valid_username(cls, value: str) -> str:
        cleaned = value.strip()
        if (
            not cleaned
            or not cleaned.isascii()
            or not cleaned[0].isalnum()
            or any(not (char.isalnum() or char == "_") for char in cleaned)
        ):
            raise ValueError("username may contain letters, numbers and underscores")
        return cleaned


class SignInIn(BaseModel):
    identifier: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=128)


class AuthUserOut(BaseModel):
    id: str
    username: str
    email: str
    created_at: datetime


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


class ClipCreateIn(BaseModel):
    """Sent after direct Cloudinary upload; the server verifies the asset."""

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
    original_filename: str
    mime_type: str
    subject: str | None
    topic: str | None
    tags: list[str]
    extracted_text_status: str | None
    analysis_confidence: float | None
    thumbnail_url: str
    preview_url: str
    created_at: datetime


class ClipDetail(ClipListItem):
    byte_size: int
    width: int
    height: int
    secure_url: str
    raw_text: str | None
    analysis_error: str | None
    ocr_used: bool
    headings: list[str]
    concepts: list[str]
    analysis_warnings: list[str]
    fields: list[FieldOut]
    actions: list[ActionOut]
    updated_at: datetime


class ClipPatchIn(BaseModel):
    title: str | None = Field(default=None, max_length=255)
    category: str | None = None
    subject: str | None = Field(default=None, max_length=120)
    topic: str | None = Field(default=None, max_length=200)
    tags: list[str] | None = Field(default=None, max_length=20)

    @field_validator("category")
    @classmethod
    def _valid_category(cls, value):
        if value is not None and value not in CATEGORIES:
            raise ValueError(f"category must be one of {CATEGORIES}")
        return value

    @field_validator("tags")
    @classmethod
    def _clean_tags(cls, value):
        if value is None:
            return value
        cleaned: list[str] = []
        for raw in value:
            tag = " ".join(str(raw).split()).strip("#,")[:40]
            if tag and tag.casefold() not in {item.casefold() for item in cleaned}:
                cleaned.append(tag)
        return cleaned[:20]


class FieldPatchItem(BaseModel):
    id: str | None = None
    name: str = Field(min_length=1, max_length=64)
    label: str = Field(default="", max_length=128)
    value: str = Field(default="", max_length=2000)


class FieldsPatchIn(BaseModel):
    fields: list[FieldPatchItem] = Field(min_length=1, max_length=60)


class AnalyzeIn(BaseModel):
    force: bool = False


class AnalysisStatusOut(BaseModel):
    clip_id: str
    status: str
    run_id: str | None
    run_status: str | None
    phase: str | None
    phase_message: str | None
    error: str | None


class ActionConfirmIn(BaseModel):
    payload: dict[str, Any] = Field(default_factory=dict)


class ActionConfirmOut(BaseModel):
    id: str
    status: str
    download_url: str | None = None
    content: str | None = None
    external_url: str | None = None


class StudyIn(BaseModel):
    mode: Literal["summary", "explain", "quiz", "flashcards"]


class StudyOut(BaseModel):
    mode: str
    items: list[dict[str, Any]]


class SettingsOut(BaseModel):
    retention_days: int
    save_extracted_text: bool


class SettingsPatchIn(BaseModel):
    retention_days: int | None = Field(default=None, ge=0, le=3650)
    save_extracted_text: bool | None = None
