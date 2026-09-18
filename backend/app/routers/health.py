"""Health check — reports liveness, DB connectivity, and whether Cloudinary
credentials are present (never the credentials themselves)."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from .. import __version__
from ..config import get_settings
from ..db import get_db
from ..schemas import HealthOut

router = APIRouter(tags=["health"])


@router.get("/api/health", response_model=HealthOut)
def health(db: Session = Depends(get_db)) -> HealthOut:
    db_status = "ok"
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        db_status = "error"
    return HealthOut(
        status="ok" if db_status == "ok" else "degraded",
        version=__version__,
        database=db_status,
        cloudinary_configured=get_settings().cloudinary_configured,
        time=datetime.now(timezone.utc),
    )
