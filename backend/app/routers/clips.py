"""Session-scoped document CRUD, search, analysis and grounded study tools."""

from __future__ import annotations

import json
import threading

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session as OrmSession

from ..config import get_settings
from ..db import get_db
from ..deps import get_session
from ..models import Action, AnalysisRun, Clip, ExtractedField, Session, utcnow
from ..schemas import (
    AnalysisStatusOut,
    AnalyzeIn,
    ClipCreateIn,
    ClipDetail,
    ClipListItem,
    ClipPatchIn,
    FieldOut,
    FieldsPatchIn,
    StudyIn,
    StudyOut,
)
from ..services import analyzer
from ..services.analysis import study
from ..services.cloudinary_service import (
    CloudinaryNotConfigured,
    CloudinaryOperationError,
    delete_asset,
    preview_url,
    thumbnail_url,
    verify_and_fetch_asset,
)

router = APIRouter(tags=["clips"])


def _json_list(value: str | None) -> list[str]:
    try:
        parsed = json.loads(value or "[]")
        return [str(item) for item in parsed if str(item).strip()] if isinstance(parsed, list) else []
    except (json.JSONDecodeError, TypeError):
        return []


def _get_clip(db: OrmSession, session: Session, clip_id: str) -> Clip:
    clip = db.get(Clip, clip_id)
    if not clip or clip.session_id != session.id:
        raise HTTPException(404, detail={"code": "not_found", "message": "We couldn't find that item."})
    return clip


def _list_item(clip: Clip) -> ClipListItem:
    settings = get_settings()
    return ClipListItem(
        id=clip.id,
        status=clip.status,
        category=clip.category,
        title=clip.title,
        original_filename=clip.original_filename,
        mime_type=clip.mime_type,
        subject=clip.subject,
        topic=clip.topic,
        tags=_json_list(clip.tags_json),
        extracted_text_status=clip.extracted_text_status,
        analysis_confidence=clip.analysis_confidence,
        thumbnail_url=thumbnail_url(settings, clip.cloudinary_public_id),
        preview_url=preview_url(settings, clip.cloudinary_public_id),
        created_at=clip.created_at,
    )


def _detail(clip: Clip) -> ClipDetail:
    common = _list_item(clip).model_dump()
    return ClipDetail(
        **common,
        byte_size=clip.byte_size,
        width=clip.width,
        height=clip.height,
        secure_url=clip.secure_url,
        raw_text=clip.raw_text,
        analysis_error=clip.analysis_error,
        ocr_used=bool(clip.ocr_used),
        headings=_json_list(clip.headings_json),
        concepts=_json_list(clip.concepts_json),
        analysis_warnings=_json_list(clip.analysis_warnings_json),
        fields=[
            FieldOut(
                id=field.id,
                name=field.name,
                label=field.label,
                value=field.value,
                confidence=field.confidence,
                user_edited=field.user_edited,
            )
            for field in clip.fields
        ],
        actions=[_action_out(action) for action in clip.actions],
        updated_at=clip.updated_at,
    )


def _action_out(action: Action):
    from ..schemas import ActionOut

    try:
        payload = json.loads(action.payload or "{}")
    except json.JSONDecodeError:
        payload = {}
    return ActionOut(
        id=action.id,
        action_type=action.action_type,
        label=action.label,
        reason=action.reason,
        primary=action.primary,
        status=action.status,
        payload=payload,
    )


@router.post("/api/clips", response_model=ClipDetail, status_code=201)
def create_clip(
    payload: ClipCreateIn,
    session: Session = Depends(get_session),
    db: OrmSession = Depends(get_db),
):
    settings = get_settings()
    if payload.mime_type not in settings.allowed_mime_types:
        raise HTTPException(415, detail={"code": "unsupported_type", "message": "Unsupported upload type."})
    if not payload.public_id.startswith(settings.cloudinary_folder + "/"):
        raise HTTPException(400, detail={"code": "bad_public_id", "message": "That upload doesn't belong to LifeClip."})
    if db.query(Clip).filter(Clip.cloudinary_public_id == payload.public_id).first():
        raise HTTPException(409, detail={"code": "duplicate", "message": "That upload has already been saved."})

    try:
        asset = verify_and_fetch_asset(settings, payload.public_id)
    except CloudinaryNotConfigured as exc:
        raise HTTPException(503, detail={"code": "cloudinary_not_configured", "message": str(exc)})
    except CloudinaryOperationError as exc:
        raise HTTPException(502, detail={"code": "cloudinary_verification", "message": str(exc)})

    if asset["bytes"] > settings.max_upload_bytes:
        delete_asset(settings, payload.public_id, asset["resource_type"])
        raise HTTPException(413, detail={"code": "file_too_large", "message": "That file is too large."})

    actual_format = str(asset["format"]).lower()
    if actual_format not in {"jpg", "jpeg", "png", "webp"}:
        delete_asset(settings, payload.public_id, asset["resource_type"])
        raise HTTPException(
            415,
            detail={"code": "type_mismatch", "message": "The uploaded asset is not a supported image."},
        )

    clip = Clip(
        session_id=session.id,
        cloudinary_public_id=asset["public_id"],
        cloudinary_resource_type=asset["resource_type"],
        secure_url=asset["secure_url"],
        format=asset["format"],
        width=asset["width"],
        height=asset["height"],
        byte_size=asset["bytes"],
        original_filename=payload.original_filename[:250],
        mime_type=payload.mime_type[:64],
        status="uploaded",
    )
    db.add(clip)
    db.commit()
    db.refresh(clip)
    return _detail(clip)


@router.get("/api/clips", response_model=list[ClipListItem])
def list_clips(
    session: Session = Depends(get_session),
    db: OrmSession = Depends(get_db),
    q: str | None = Query(default=None, max_length=120),
    category: str | None = Query(default=None, max_length=24),
    limit: int = Query(default=100, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    query = db.query(Clip).filter(Clip.session_id == session.id)
    if category:
        query = query.filter(Clip.category == category)
    if q and q.strip():
        like = f"%{q.strip()}%"
        query = query.filter(or_(
            Clip.title.ilike(like),
            Clip.original_filename.ilike(like),
            Clip.raw_text.ilike(like),
            Clip.subject.ilike(like),
            Clip.topic.ilike(like),
            Clip.tags_json.ilike(like),
            Clip.headings_json.ilike(like),
            Clip.concepts_json.ilike(like),
            Clip.fields.any(ExtractedField.value.ilike(like)),
        ))
    clips = query.order_by(Clip.created_at.desc()).offset(offset).limit(limit).all()
    return [_list_item(clip) for clip in clips]


@router.get("/api/clips/{clip_id}", response_model=ClipDetail)
def get_clip(
    clip_id: str,
    session: Session = Depends(get_session),
    db: OrmSession = Depends(get_db),
):
    return _detail(_get_clip(db, session, clip_id))


@router.patch("/api/clips/{clip_id}", response_model=ClipDetail)
def patch_clip(
    clip_id: str,
    payload: ClipPatchIn,
    session: Session = Depends(get_session),
    db: OrmSession = Depends(get_db),
):
    clip = _get_clip(db, session, clip_id)
    if payload.title is not None:
        clip.title = payload.title.strip()[:250] or clip.title
    if payload.category is not None:
        clip.category = payload.category
    if payload.subject is not None:
        clip.subject = payload.subject.strip()[:120] or None
    if payload.topic is not None:
        clip.topic = payload.topic.strip()[:200] or None
    if payload.tags is not None:
        clip.tags_json = json.dumps(payload.tags, ensure_ascii=False)
    clip.updated_at = utcnow()
    db.commit()
    db.refresh(clip)
    return _detail(clip)


@router.patch("/api/clips/{clip_id}/fields", response_model=ClipDetail)
def patch_fields(
    clip_id: str,
    payload: FieldsPatchIn,
    session: Session = Depends(get_session),
    db: OrmSession = Depends(get_db),
):
    clip = _get_clip(db, session, clip_id)
    existing = {field.id: field for field in clip.fields}
    kept: set[str] = set()
    max_pos = max((field.position for field in clip.fields), default=0)
    for item in payload.fields:
        value = item.value.strip()
        if item.id and item.id in existing:
            field = existing[item.id]
            field.value = value
            field.user_edited = True
            field.confidence = 1.0
            kept.add(field.id)
        else:
            max_pos += 1
            db.add(ExtractedField(
                clip_id=clip.id,
                name=item.name[:64],
                label=(item.label or item.name.replace("_", " ").title())[:128],
                value=value,
                confidence=1.0,
                position=max_pos,
                user_edited=True,
            ))
    for field in clip.fields:
        if field.id not in kept and not any(item.id == field.id for item in payload.fields):
            db.delete(field)
    clip.updated_at = utcnow()
    db.commit()
    db.refresh(clip)
    return _detail(clip)


@router.post("/api/clips/{clip_id}/analyze", response_model=AnalysisStatusOut, status_code=202)
def analyze(
    clip_id: str,
    payload: AnalyzeIn | None = None,
    session: Session = Depends(get_session),
    db: OrmSession = Depends(get_db),
):
    clip = _get_clip(db, session, clip_id)
    force = bool(payload and payload.force)
    active = next((run for run in clip.runs if run.status in ("queued", "running")), None)
    if active:
        return _analysis_status(clip, active)
    if clip.status in ("ready", "partial") and not force:
        return _analysis_status(clip, clip.runs[-1] if clip.runs else None)

    settings = get_settings()
    if not settings.cloudinary_configured:
        raise HTTPException(503, detail={"code": "cloudinary_not_configured", "message": "Cloudinary is not configured on the server yet."})
    attempt = len(clip.runs) + 1
    if attempt > 6:
        raise HTTPException(429, detail={"code": "too_many_attempts", "message": "We've tried this a few times. Please wait, then retry."})
    run = AnalysisRun(clip_id=clip.id, attempt=attempt, status="queued", phase="queued")
    clip.status = "queued"
    clip.analysis_error = None
    db.add(run)
    db.commit()
    db.refresh(run)
    threading.Thread(
        target=analyzer.run_analysis,
        args=(clip.id, run.id, settings),
        daemon=True,
        name=f"analysis-{clip.id[:8]}",
    ).start()
    return _analysis_status(clip, run)


@router.get("/api/clips/{clip_id}/analysis", response_model=AnalysisStatusOut)
def analysis_status(
    clip_id: str,
    session: Session = Depends(get_session),
    db: OrmSession = Depends(get_db),
):
    clip = _get_clip(db, session, clip_id)
    return _analysis_status(clip, clip.runs[-1] if clip.runs else None)


def _analysis_status(clip: Clip, run: AnalysisRun | None) -> AnalysisStatusOut:
    error = run.error if run and run.status == "failed" else None
    return AnalysisStatusOut(
        clip_id=clip.id,
        status=clip.status,
        run_id=run.id if run else None,
        run_status=run.status if run else None,
        phase=run.phase if run else None,
        phase_message=analyzer.PHASES.get(run.phase) if run else None,
        error=error or ("Analysis failed. Please try again." if run and run.status == "failed" else None),
    )


@router.post("/api/clips/{clip_id}/study", response_model=StudyOut)
def study_tools(
    clip_id: str,
    payload: StudyIn,
    session: Session = Depends(get_session),
    db: OrmSession = Depends(get_db),
):
    clip = _get_clip(db, session, clip_id)
    text = (clip.raw_text or "").strip()
    if not text:
        raise HTTPException(422, detail={"code": "no_text", "message": "There's not enough readable text for this yet."})
    function = {
        "summary": study.summarize,
        "explain": study.explain,
        "quiz": study.quiz,
        "flashcards": study.flashcards,
    }[payload.mode]
    items = function(text)
    if not items:
        raise HTTPException(422, detail={"code": "no_content", "message": "We couldn't build this from the extracted text. Try a clearer, longer file."})
    return StudyOut(mode=payload.mode, items=items)


@router.delete("/api/clips/{clip_id}")
def delete_clip(
    clip_id: str,
    session: Session = Depends(get_session),
    db: OrmSession = Depends(get_db),
):
    clip = _get_clip(db, session, clip_id)
    cloud_deleted = delete_asset(get_settings(), clip.cloudinary_public_id, clip.cloudinary_resource_type)
    db.delete(clip)
    db.commit()
    return {
        "deleted": True,
        "cloudinary_asset_deleted": cloud_deleted,
        "message": (
            "Deleted from LifeClip and Cloudinary."
            if cloud_deleted
            else "Deleted from LifeClip. The Cloudinary copy could not be removed."
        ),
    }
