"""Runs analysis for a clip: downloads the asset, executes the pipeline,
persists results. Designed to run in a background thread with its own DB
session — always leaves the clip in a safe, truthful state.

Idempotency lives in the router (the run row is created before the thread
starts); this worker only ever completes an existing run.
"""

from __future__ import annotations

import json
import logging
import traceback

import requests
from sqlalchemy.orm import Session as OrmSession

from ..config import Settings
from ..db import SessionLocal
from ..models import Action, AnalysisRun, Clip, ExtractedField, utcnow
from .analysis.pipeline import run_pipeline
from .cloudinary_service import analysis_url

log = logging.getLogger("lifeclip.analysis")

PHASES = {
    "queued": "Queued",
    "fetching": "Fetching your image",
    "understanding": "Understanding",
    "extracting": "Finding useful information",
    "actions": "Preparing actions",
    "done": "Done",
}


def _set_phase(db: OrmSession, run: AnalysisRun, phase: str) -> None:
    run.phase = phase
    db.commit()


def run_analysis(clip_id: str, run_id: str, settings: Settings) -> None:
    db = SessionLocal()
    try:
        clip = db.get(Clip, clip_id)
        run = db.get(AnalysisRun, run_id)
        if not clip or not run:
            return
        run.status = "running"
        run.started_at = utcnow()
        _set_phase(db, run, "fetching")
        clip.status = "analyzing"
        db.commit()

        # 1) Download the image from its Cloudinary delivery URL.
        url = analysis_url(settings, clip.cloudinary_public_id, clip.format)
        try:
            resp = requests.get(
                url, timeout=settings.image_fetch_timeout_seconds, stream=True
            )
            resp.raise_for_status()
            content = resp.content
            if len(content) > 25 * 1024 * 1024:
                raise ValueError("image too large after transform")
        except Exception:
            log.warning("asset fetch failed for clip %s", clip_id)
            raise RuntimeError(
                "We couldn't download your image from Cloudinary to analyze it. "
                "Please check your connection and try again."
            )

        # 2) Understand (OCR + classify).
        _set_phase(db, run, "understanding")
        result = run_pipeline(content, max_chars=settings.max_ocr_chars)

        # 3) Finding information (already computed — phase reported truthfully
        #    before persisting structured output).
        _set_phase(db, run, "extracting")

        clip.category = result.category
        clip.title = result.title[:250]
        if clip.session and clip.session.settings and not clip.session.settings.save_extracted_text:
            clip.raw_text = None
        else:
            clip.raw_text = result.text or None

        # Replace previous extraction (retry-safe).
        clip.fields.clear()
        clip.actions.clear()
        db.flush()
        for i, f in enumerate(result.fields):
            db.add(ExtractedField(
                clip_id=clip.id, name=f.name, label=f.label, value=f.value,
                confidence=f.confidence, position=i,
            ))

        # 4) Preparing actions.
        _set_phase(db, run, "actions")
        for i, a in enumerate(result.actions):
            payload: dict = {}
            if a.action_type in ("calendar", "reminder"):
                payload = {
                    "title": clip.title or "",
                    "date": fields_val(result.fields, "date"),
                    "time": fields_val(result.fields, "time"),
                    "location": fields_val(result.fields, "location"),
                    "reminder_minutes": 60 if a.action_type == "reminder" else None,
                }
            elif a.action_type == "directions":
                payload = {"query": fields_val(result.fields, "location")}
            elif a.action_type == "search":
                payload = {"query": fields_val(result.fields, "model") or clip.title or ""}
            elif a.action_type == "open_link":
                payload = {"url": fields_val(result.fields, "url")}
            db.add(Action(
                clip_id=clip.id, action_type=a.action_type, label=a.label,
                reason=a.reason, primary=a.primary, status="suggested",
                payload=json.dumps(payload), position=i,
            ))

        clip.status = "partial" if result.partial else "ready"
        clip.analysis_error = None
        warnings = result.warnings
        if warnings:
            # Store warnings with the run for the status endpoint to surface.
            run.error = "WARNINGS::" + json.dumps(warnings)
        run.status = "partial" if result.partial else "succeeded"
        run.completed_at = utcnow()
        _set_phase(db, run, "done")
        db.commit()
    except Exception as exc:
        db.rollback()
        _mark_failed(db, clip_id, run_id, exc)
    finally:
        db.close()


def fields_val(fields, name: str) -> str:
    for f in fields:
        if f.name == name:
            return f.value
    return ""


def _mark_failed(db: OrmSession, clip_id: str, run_id: str, exc: Exception) -> None:
    try:
        clip = db.get(Clip, clip_id)
        run = db.get(AnalysisRun, run_id)
        message = str(exc) if str(exc) else "Something went wrong while analyzing. Please try again."
        if "'signature'" in message or "credentials" in message.lower():
            message = "The server couldn't reach Cloudinary. Please try again later."
        if run:
            run.status = "failed"
            run.error = message[:500]
            run.phase = "failed"
            run.completed_at = utcnow()
        if clip:
            clip.status = "failed"
            clip.analysis_error = message[:500]
        db.commit()
        log.error("analysis failed for clip %s: %s\n%s", clip_id, exc, traceback.format_exc())
    except Exception:  # pragma: no cover - last-resort guard
        log.exception("failed to mark analysis run failed")
        db.rollback()
