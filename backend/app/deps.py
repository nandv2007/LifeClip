"""Shared FastAPI dependencies — anonymous session authentication.

LifeClip does not require an account. The frontend generates a random token
once (stored in the browser's localStorage) and sends it as a header with
each request. Clips belong to the session; a user can only ever see their own
session's clips through this dependency.
"""

import re

from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session as OrmSession

from .config import get_settings
from .db import get_db
from .models import Session, utcnow

_TOKEN_RE = re.compile(r"^[A-Za-z0-9_-]{16,128}$")


def get_session(
    x_lifeclip_session: str | None = Header(default=None),
    db: OrmSession = Depends(get_db),
) -> Session:
    header_name = get_settings().session_header
    if not x_lifeclip_session:
        raise HTTPException(
            status_code=401,
            detail={
                "code": "no_session",
                "message": "Your session could not be found. Please reload the app.",
            },
        )
    if not _TOKEN_RE.match(x_lifeclip_session):
        raise HTTPException(
            status_code=401,
            detail={
                "code": "bad_session",
                "message": "Your session looks invalid. Please reload the app.",
            },
        )
    session = db.get(Session, x_lifeclip_session)
    if session is None:
        session = Session(id=x_lifeclip_session)
        db.add(session)
        db.commit()
    session.last_seen_at = utcnow()
    db.commit()
    _ = header_name
    return session
