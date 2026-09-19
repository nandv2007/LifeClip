"""Shared FastAPI dependencies for account and data-session isolation.

The browser still sends its random pre-account token so a new account can
claim existing local clips. Once a session belongs to a user, only a valid
HttpOnly login cookie can access it; knowing the old browser token is not
sufficient.
"""

from __future__ import annotations

import re

from fastapi import Depends, Header, HTTPException, Request
from sqlalchemy.orm import Session as OrmSession

from .db import get_db
from .models import Session, User, utcnow
from .services.auth_service import authenticated_session

_TOKEN_RE = re.compile(r"^[A-Za-z0-9_-]{16,128}$")


def header_session(
    token: str | None,
    db: OrmSession,
    *,
    create: bool,
) -> Session | None:
    if not token or not _TOKEN_RE.fullmatch(token):
        return None
    session = db.get(Session, token)
    if session is None and create:
        session = Session(id=token)
        db.add(session)
        db.flush()
    return session


def get_current_user(
    request: Request,
    db: OrmSession = Depends(get_db),
) -> User:
    login = authenticated_session(request, db)
    if login is None:
        raise HTTPException(
            status_code=401,
            detail={"code": "not_authenticated", "message": "Please sign in to continue."},
        )
    return login.user


def get_session(
    request: Request,
    x_lifeclip_session: str | None = Header(default=None),
    db: OrmSession = Depends(get_db),
) -> Session:
    login = authenticated_session(request, db)
    if login is not None:
        session = db.query(Session).filter(Session.user_id == login.user_id).one_or_none()
        if session is None:
            # Defensive recovery for a partially migrated account.
            session = Session(user_id=login.user_id)
            db.add(session)
            db.commit()
            db.refresh(session)
        session.last_seen_at = utcnow()
        db.commit()
        return session

    if not x_lifeclip_session:
        raise HTTPException(
            status_code=401,
            detail={
                "code": "no_session",
                "message": "Please sign in to continue.",
            },
        )
    if not _TOKEN_RE.fullmatch(x_lifeclip_session):
        raise HTTPException(
            status_code=401,
            detail={
                "code": "bad_session",
                "message": "Your browser session is invalid. Please reload the app.",
            },
        )

    session = header_session(x_lifeclip_session, db, create=True)
    assert session is not None
    if session.user_id is not None:
        raise HTTPException(
            status_code=401,
            detail={"code": "not_authenticated", "message": "Please sign in to continue."},
        )
    session.last_seen_at = utcnow()
    db.commit()
    return session
