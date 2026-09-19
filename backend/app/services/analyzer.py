"""Cloudinary media -> extraction/OCR -> classification -> persistence worker."""

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
    "fetching": "Downloading original",
    "extracting_text": "Extracting text",
    "classifying": "Classifying",
    "organizing": "Organizing details",
    "done": "Ready",
}


def _set_phase(db: OrmSession, run: AnalysisRun, phase: str) -> None:
    run.phase = phase
    db.commit()


def _download(url: str, settings: Settings) -> bytes:
    limit = settings.max_upload_bytes + 1024 * 1024
    try:
        with requests.get(url, timeout=settings.image_fetch_timeout_seconds, stream=True) as response:
            response.raise_for_status()
            announced = int(response.headers.get("content-length", "0") or 0)
            if announced > limit:
                raise ValueError("asset exceeds safe processing limit")
            chunks: list[bytes] = []
            total = 0
            for chunk in response.iter_content(128 * 1024):
                if not chunk:
                    continue
                total += len(chunk)
                if total > limit:
                    raise ValueError("asset exceeds safe processing limit")
                chunks.append(chunk)
            return b"".join(chunks)
    except Exception as exc:
        raise RuntimeError(
            "We couldn't download your file from Cloudinary to analyze it. "
            "Please check your connection and try again."
        ) from exc


def run_analysis(clip_id: str, run_id: str, settings: Settings) -> None:
    db = SessionLocal()
    try:
        clip = db.get(Clip, clip_id)
        run = db.get(AnalysisRun, run_id)
        if not clip or not run:
            return
        run.status = "running"
        run.provider = "local-image-ocr-rules/v2"
        run.started_at = utcnow()
        clip.status = "analyzing"
        _set_phase(db, run, "fetching")

        # Download a bounded Cloudinary image transform for local OCR.
        url = analysis_url(settings, clip.cloudinary_public_id, clip.format)
        content = _download(url, settings)

        def progress(phase: str) -> None:
            _set_phase(db, run, phase)

        result = run_pipeline(
            content,
            max_chars=settings.max_ocr_chars,
            phase_callback=progress,
        )

        clip.category = result.category
        clip.title = result.title[:250]
        clip.subject = result.subject or None
        clip.topic = result.topic or None
        clip.headings_json = json.dumps(result.headings, ensure_ascii=False)
        clip.concepts_json = json.dumps(result.concepts, ensure_ascii=False)
        clip.extracted_text_status = result.text_status
        clip.ocr_used = result.ocr_used
        clip.analysis_confidence = result.category_confidence
        clip.analysis_warnings_json = json.dumps(result.warnings, ensure_ascii=False)
        if clip.session and clip.session.settings and not clip.session.settings.save_extracted_text:
            clip.raw_text = None
        else:
            clip.raw_text = result.text or None

        # Replace prior extraction/actions so retries are idempotent.
        clip.fields.clear()
        clip.actions.clear()
        db.flush()
        for index, field in enumerate(result.fields):
            db.add(ExtractedField(
                clip_id=clip.id,
                name=field.name,
                label=field.label,
                value=field.value,
                confidence=field.confidence,
                position=index,
            ))

        for index, action in enumerate(result.actions):
            payload: dict = {}
            if action.action_type in ("calendar", "reminder"):
                payload = {
                    "title": clip.title or "",
                    "date": fields_val(result.fields, "date"),
                    "time": fields_val(result.fields, "time"),
                    "location": fields_val(result.fields, "location"),
                    "reminder_minutes": 60 if action.action_type == "reminder" else None,
                }
            elif action.action_type == "directions":
                payload = {"query": fields_val(result.fields, "location")}
            elif action.action_type == "search":
                payload = {"query": fields_val(result.fields, "model") or clip.title or ""}
            elif action.action_type == "open_link":
                payload = {"url": fields_val(result.fields, "url")}
            db.add(Action(
                clip_id=clip.id,
                action_type=action.action_type,
                label=action.label,
                reason=action.reason,
                primary=action.primary,
                status="suggested",
                payload=json.dumps(payload),
                position=index,
            ))

        clip.status = "partial" if result.partial else "ready"
        clip.analysis_error = None
        if result.warnings:
            run.error = "WARNINGS::" + json.dumps(result.warnings)
        run.status = "partial" if result.partial else "succeeded"
        run.completed_at = utcnow()
        _set_phase(db, run, "done")
    except Exception as exc:
        db.rollback()
        _mark_failed(db, clip_id, run_id, exc)
    finally:
        db.close()


def fields_val(fields, name: str) -> str:
    for field in fields:
        if field.name == name:
            return field.value
    return ""


def _mark_failed(db: OrmSession, clip_id: str, run_id: str, exc: Exception) -> None:
    try:
        clip = db.get(Clip, clip_id)
        run = db.get(AnalysisRun, run_id)
        message = str(exc) or "Something went wrong while analyzing. Please try again."
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
    except Exception:  # pragma: no cover
        log.exception("failed to mark analysis run failed")
        db.rollback()
