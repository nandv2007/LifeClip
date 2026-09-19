"""Per-session settings + full data deletion ("Delete my data")."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session as OrmSession

from ..config import get_settings
from ..db import get_db
from ..deps import get_session
from ..models import Clip, Session, SessionSettings
from ..schemas import SettingsOut, SettingsPatchIn
from ..services.cloudinary_service import delete_asset

router = APIRouter(tags=["settings"])


def _get_or_create(db: OrmSession, session: Session) -> SessionSettings:
    s = session.settings
    if s is None:
        s = SessionSettings(
            session_id=session.id,
            retention_days=get_settings().retention_days,
        )
        db.add(s)
        db.commit()
        db.refresh(s)
    return s


@router.get("/api/settings", response_model=SettingsOut)
def read_settings(session: Session = Depends(get_session), db: OrmSession = Depends(get_db)):
    s = _get_or_create(db, session)
    return SettingsOut(retention_days=s.retention_days, save_extracted_text=s.save_extracted_text)


@router.patch("/api/settings", response_model=SettingsOut)
def patch_settings(payload: SettingsPatchIn,
                   session: Session = Depends(get_session),
                   db: OrmSession = Depends(get_db)):
    s = _get_or_create(db, session)
    if payload.retention_days is not None:
        s.retention_days = payload.retention_days
    if payload.save_extracted_text is not None:
        s.save_extracted_text = payload.save_extracted_text
        if not s.save_extracted_text:
            # Respect immediately: drop previously stored extracted text.
            db.query(Clip).filter(Clip.session_id == session.id).update(
                {Clip.raw_text: None}, synchronize_session=False
            )
    db.commit()
    db.refresh(s)
    return SettingsOut(retention_days=s.retention_days, save_extracted_text=s.save_extracted_text)


@router.delete("/api/account")
def delete_account(session: Session = Depends(get_session), db: OrmSession = Depends(get_db)):
    """Delete every clip (and its Cloudinary asset) plus the session itself."""
    settings = get_settings()
    clips = db.query(Clip).filter(Clip.session_id == session.id).all()
    cloud_deleted = 0
    for c in clips:
        if delete_asset(settings, c.cloudinary_public_id, c.cloudinary_resource_type):
            cloud_deleted += 1
    db.delete(session)  # cascades to clips, fields, actions, runs, settings
    db.commit()
    return {
        "deleted": True,
        "clips_removed": len(clips),
        "cloudinary_assets_deleted": cloud_deleted,
        "message": "All of your LifeClip data has been deleted.",
    }
