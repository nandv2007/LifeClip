"""Clips: create (after Cloudinary upload), list, detail, edit, analyze, study,
delete — all scoped to the caller's anonymous session."""

from __future__ import annotations

import json
import re
import threading

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session as OrmSession

from ..config import get_settings
from ..db import get_db
from ..deps import get_session
from ..models import (
    Action,
    AnalysisRun,
    Clip,
    ExtractedField,
    Session,
    SessionSettings,
    utcnow,
)
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

WARN_RE = re.compile(r"^WARNINGS::")


# ------------------------------------------------------------------ helpers

def _get_clip(db: OrmSession, session: Session, clip_id: str) -> Clip:
    clip = db.get(Clip, clip_id)
    if not clip or clip.session_id != session.id:
        raise HTTPException(
            status_code=404,
            detail={"code": "not_found", "message": "We couldn't find that item."},
        )
    return clip


def _list_item(clip: Clip) -> ClipListItem:
    s = get_settings()
    return ClipListItem(
        id=clip.id,
        status=clip.status,
        category=clip.category,
        title=clip.title,
        thumbnail_url=thumbnail_url(s, clip.cloudinary_public_id),
        preview_url=preview_url(s, clip.cloudinary_public_id),
        created_at=clip.created_at,
    )


def _detail(clip: Clip) -> ClipDetail:
    s = get_settings()
    return ClipDetail(
        id=clip.id,
        status=clip.status,
        category=clip.category,
        title=clip.title,
        original_filename=clip.original_filename,
        mime_type=clip.mime_type,
        byte_size=clip.byte_size,
        width=clip.width,
        height=clip.height,
        secure_url=clip.secure_url,
        preview_url=preview_url(s, clip.cloudinary_public_id),
        thumbnail_url=thumbnail_url(s, clip.cloudinary_public_id),
        raw_text=clip.raw_text,
        analysis_error=clip.analysis_error,
        fields=[
            FieldOut(id=f.id, name=f.name, label=f.label, value=f.value,
                     confidence=f.confidence, user_edited=f.user_edited)
            for f in clip.fields
        ],
        actions=[_action_out(a) for a in clip.actions],
        created_at=clip.created_at,
        updated_at=clip.updated_at,
    )


def _action_out(a: Action):
    from ..schemas import ActionOut

    try:
        payload = json.loads(a.payload or "{}")
    except json.JSONDecodeError:
        payload = {}
    return ActionOut(
        id=a.id, action_type=a.action_type, label=a.label, reason=a.reason,
        primary=a.primary, status=a.status, payload=payload,
    )


# ------------------------------------------------------------------ create

@router.post("/api/clips", response_model=ClipDetail, status_code=201)
def create_clip(payload: ClipCreateIn,
                session: Session = Depends(get_session),
                db: OrmSession = Depends(get_db)):
    settings = get_settings()
    if not payload.public_id.startswith(settings.cloudinary_folder + "/"):
        raise HTTPException(
            status_code=400,
            detail={"code": "bad_public_id", "message": "That upload doesn't belong to LifeClip."},
        )
    if db.query(Clip).filter(Clip.cloudinary_public_id == payload.public_id).first():
        raise HTTPException(
            status_code=409,
            detail={"code": "duplicate", "message": "That upload has already been saved."},
        )

    # Verify against Cloudinary's Admin API — never trust client claims.
    try:
        asset = verify_and_fetch_asset(settings, payload.public_id)
    except CloudinaryNotConfigured as exc:
        raise HTTPException(503, detail={"code": "cloudinary_not_configured", "message": str(exc)})
    except CloudinaryOperationError as exc:
        raise HTTPException(502, detail={"code": "cloudinary_verification", "message": str(exc)})

    if asset["bytes"] > settings.max_upload_bytes:
        delete_asset(settings, payload.public_id)
        raise HTTPException(413, detail={"code": "file_too_large",
                                         "message": "That file is too large."})

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


# ------------------------------------------------------------------ list/read

@router.get("/api/clips", response_model=list[ClipListItem])
def list_clips(
    session: Session = Depends(get_session),
    db: OrmSession = Depends(get_db),
    q: str | None = Query(default=None, max_length=120),
    category: str | None = Query(default=None, max_length=24),
    limit: int = Query(default=60, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    query = db.query(Clip).filter(Clip.session_id == session.id)
    if category:
        query = query.filter(Clip.category == category)
    if q:
        like = f"%{q.strip()}%"
        query = query.filter(or_(Clip.title.ilike(like), Clip.raw_text.ilike(like)))
    clips = query.order_by(Clip.created_at.desc()).offset(offset).limit(limit).all()
    return [_list_item(c) for c in clips]


@router.get("/api/clips/{clip_id}", response_model=ClipDetail)
def get_clip(clip_id: str,
             session: Session = Depends(get_session),
             db: OrmSession = Depends(get_db)):
    return _detail(_get_clip(db, session, clip_id))


# ------------------------------------------------------------------ edit

@router.patch("/api/clips/{clip_id}", response_model=ClipDetail)
def patch_clip(clip_id: str, payload: ClipPatchIn,
               session: Session = Depends(get_session),
               db: OrmSession = Depends(get_db)):
    clip = _get_clip(db, session, clip_id)
    if payload.title is not None:
        clip.title = payload.title.strip()[:250] or clip.title
    if payload.category is not None:
        clip.category = payload.category
    clip.updated_at = utcnow()
    db.commit()
    db.refresh(clip)
    return _detail(clip)


@router.patch("/api/clips/{clip_id}/fields", response_model=ClipDetail)
def patch_fields(clip_id: str, payload: FieldsPatchIn,
                 session: Session = Depends(get_session),
                 db: OrmSession = Depends(get_db)):
    clip = _get_clip(db, session, clip_id)
    existing = {f.id: f for f in clip.fields}
    kept: set[str] = set()
    max_pos = max((f.position for f in clip.fields), default=0)

    for item in payload.fields:
        value = item.value.strip()
        if item.id and item.id in existing:
            f = existing[item.id]
            f.value = value
            f.user_edited = True
            f.confidence = 1.0  # user-confirmed value
            kept.add(f.id)
        else:
            max_pos += 1
            db.add(ExtractedField(
                clip_id=clip.id, name=item.name[:64],
                label=(item.label or item.name.replace("_", " ").title())[:128],
                value=value, confidence=1.0, position=max_pos, user_edited=True,
            ))
    # Fields omitted from the payload are treated as deleted by the user.
    for f in clip.fields:
        if f.id not in kept and not any(i.id == f.id for i in payload.fields):
            db.delete(f)
    clip.updated_at = utcnow()
    db.commit()
    db.refresh(clip)
    return _detail(clip)


# ------------------------------------------------------------------ analyze

@router.post("/api/clips/{clip_id}/analyze", response_model=AnalysisStatusOut, status_code=202)
def analyze(clip_id: str, payload: AnalyzeIn | None = None,
            session: Session = Depends(get_session),
            db: OrmSession = Depends(get_db)):
    """Kick off analysis. IDEMPOTENT:
      - an active (queued/running) run is returned as-is (refresh never duplicates)
      - a finished clip returns its result (unless force=true retry)
    """
    clip = _get_clip(db, session, clip_id)
    force = bool(payload and payload.force)

    active = next(
        (r for r in clip.runs if r.status in ("queued", "running")), None
    )
    if active:
        return _analysis_status(clip, active)

    if clip.status in ("ready", "partial") and not force:
        last = clip.runs[-1] if clip.runs else None
        return _analysis_status(clip, last)

    settings = get_settings()
    if not settings.cloudinary_configured:
        raise HTTPException(
            503,
            detail={"code": "cloudinary_not_configured",
                    "message": "Cloudinary is not configured on the server yet."},
        )

    attempt = len(clip.runs) + 1
    if attempt > 6:
        raise HTTPException(
            429,
            detail={"code": "too_many_attempts",
                    "message": "We've tried this a few times. Please wait a bit, then retry."},
        )
    run = AnalysisRun(clip_id=clip.id, attempt=attempt, status="queued", phase="queued")
    clip.status = "queued"
    clip.analysis_error = None
    db.add(run)
    db.commit()
    db.refresh(run)

    thread = threading.Thread(
        target=analyzer.run_analysis,
        args=(clip.id, run.id, settings),
        daemon=True,
        name=f"analysis-{clip.id[:8]}",
    )
    thread.start()
    return _analysis_status(clip, run)


@router.get("/api/clips/{clip_id}/analysis", response_model=AnalysisStatusOut)
def analysis_status(clip_id: str,
                    session: Session = Depends(get_session),
                    db: OrmSession = Depends(get_db)):
    clip = _get_clip(db, session, clip_id)
    last = clip.runs[-1] if clip.runs else None
    return _analysis_status(clip, last)


def _analysis_status(clip: Clip, run: AnalysisRun | None) -> AnalysisStatusOut:
    error = None
    if run and run.status == "failed":
        error = run.error or "Analysis failed. Please try again."
    return AnalysisStatusOut(
        clip_id=clip.id,
        status=clip.status,
        run_id=run.id if run else None,
        run_status=run.status if run else None,
        phase=run.phase if run else None,
        phase_message=analyzer.PHASES.get(run.phase, None) if run else None,
        error=error,
    )


# ------------------------------------------------------------------ study tools

@router.post("/api/clips/{clip_id}/study", response_model=StudyOut)
def study_tools(clip_id: str, payload: StudyIn,
                session: Session = Depends(get_session),
                db: OrmSession = Depends(get_db)):
    clip = _get_clip(db, session, clip_id)
    text = (clip.raw_text or "").strip()
    if not text:
        raise HTTPException(
            422,
            detail={"code": "no_text",
                    "message": "There's not enough readable text for this yet."},
        )
    fn = {"summary": study.summarize, "explain": study.explain,
          "quiz": study.quiz, "flashcards": study.flashcards}[payload.mode]
    items = fn(text)
    if not items:
        raise HTTPException(
            422,
            detail={"code": "no_content",
                    "message": "We couldn't build this from the extracted text. "
                               "Try a photo with clearer, longer text."},
        )
    return StudyOut(mode=payload.mode, items=items)


# ------------------------------------------------------------------ delete

@router.delete("/api/clips/{clip_id}")
def delete_clip(clip_id: str,
                session: Session = Depends(get_session),
                db: OrmSession = Depends(get_db)):
    clip = _get_clip(db, session, clip_id)
    cloud_deleted = delete_asset(get_settings(), clip.cloudinary_public_id)
    db.delete(clip)  # cascades to fields/actions/runs
    db.commit()
    return {
        "deleted": True,
        "cloudinary_asset_deleted": cloud_deleted,
        "message": ("Deleted from LifeClip and Cloudinary." if cloud_deleted
                    else "Deleted from LifeClip. The Cloudinary copy could not be "
                         "removed (check server credentials/connection)."),
    }
