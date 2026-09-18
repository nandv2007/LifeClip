"""LifeClip API — application entry point.

Security posture:
  * consistent JSON error envelope, no stack traces, no secrets in responses
  * CORS restricted via ALLOWED_ORIGINS (permissive only for local dev)
  * logging never includes the Cloudinary secret or raw extracted text
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from . import __version__
from .config import get_settings
from .db import SessionLocal, engine, init_db
from .routers import actions, clips, health, settings as settings_router, uploads

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
# Silence noisy libs; never log request bodies anyway.
logging.getLogger("urllib3").setLevel(logging.WARNING)
log = logging.getLogger("lifeclip")

app = FastAPI(
    title="LifeClip API",
    version=__version__,
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
    # Never echo internal exceptions to clients:
    default_response_class=JSONResponse,
)

_s = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=_s.cors_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", _s.session_header],
)
app.add_middleware(GZipMiddleware, minimum_size=1024)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    resp = await call_next(request)
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["X-Frame-Options"] = "DENY"
    resp.headers["Referrer-Policy"] = "no-referrer"
    resp.headers["Permissions-Policy"] = "camera=(self), microphone=()"
    return resp


# ------------------------------------------------------------- error envelope

def _envelope(code: str, message: str) -> dict:
    return {"error": {"code": code, "message": message}}


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Consistent envelope: {"error": {"code", "message"}} for API clients."""
    detail = exc.detail
    if isinstance(detail, dict) and "code" in detail and "message" in detail:
        body = _envelope(str(detail["code"]), str(detail["message"]))
    elif isinstance(detail, str):
        body = _envelope("error", detail)
    else:
        body = _envelope("error", "The request could not be completed. Please try again.")
    headers = getattr(exc, "headers", None) or {}
    return JSONResponse(status_code=exc.status_code, content=body, headers=headers)


@app.exception_handler(RequestValidationError)
async def validation_handler(request: Request, exc: RequestValidationError):
    log.info("validation error on %s: %s", request.url.path, exc.errors()[0] if exc.errors() else "")
    return JSONResponse(
        status_code=422,
        content=_envelope("invalid_request", "Some of the information sent was invalid. Please try again."),
    )


@app.exception_handler(Exception)
async def unhandled_handler(request: Request, exc: Exception):
    log.exception("unhandled error on %s", request.url.path)
    return JSONResponse(
        status_code=500,
        content=_envelope("server_error", "Something went wrong on our side. Please try again."),
    )


# --------------------------------------------------------------- lifecycle

def _recover_interrupted_runs() -> None:
    """Runs left 'queued/running' by a restart become honestly failed, so the
    UI offers 'Try again' instead of spinning forever."""
    from .models import AnalysisRun, Clip, utcnow

    db = SessionLocal()
    try:
        stale = db.query(AnalysisRun).filter(AnalysisRun.status.in_(["queued", "running"])).all()
        for run in stale:
            run.status = "failed"
            run.phase = "failed"
            run.error = "The analysis was interrupted by a server restart. Please try again."
            run.completed_at = utcnow()
            clip = db.get(Clip, run.clip_id)
            if clip and clip.status in ("queued", "analyzing"):
                clip.status = "failed"
                clip.analysis_error = run.error
        if stale:
            log.info("recovered %d interrupted analysis run(s)", len(stale))
        db.commit()
    finally:
        db.close()


def _purge_expired() -> None:
    """Retention: permanently delete clips older than each session's setting."""
    from .models import Clip, SessionSettings
    from .services.cloudinary_service import delete_asset

    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)
        rows = (
            db.query(Clip, SessionSettings.retention_days)
            .join(SessionSettings, SessionSettings.session_id == Clip.session_id)
            .filter(SessionSettings.retention_days > 0)
            .all()
        )
        settings = get_settings()
        purged = 0
        for clip, days in rows:
            created = clip.created_at
            if created and created.tzinfo is None:
                created = created.replace(tzinfo=timezone.utc)
            if created and now - created > timedelta(days=days):
                delete_asset(settings, clip.cloudinary_public_id)
                db.delete(clip)
                purged += 1
        if purged:
            log.info("retention purge removed %d clip(s)", purged)
        db.commit()
    except Exception:
        db.rollback()
        log.exception("retention purge failed")
    finally:
        db.close()


@app.on_event("startup")
def startup() -> None:
    init_db()
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    _recover_interrupted_runs()
    _purge_expired()
    log.info(
        "LifeClip API v%s up — db=%s cloudinary=%s",
        __version__,
        "postgresql" if "postgres" in _s.resolved_database_url else "sqlite",
        "configured" if _s.cloudinary_configured else "NOT-configured",
    )


# ----------------------------------------------------------------- routers

app.include_router(health.router)
app.include_router(uploads.router)
app.include_router(clips.router)
app.include_router(actions.router)
app.include_router(settings_router.router)


# ------------------------------------------- optional built frontend (prod)
_dist = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"
if _dist.is_dir():
    app.mount("/", StaticFiles(directory=_dist, html=True), name="frontend")
