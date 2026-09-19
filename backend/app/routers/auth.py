"""Basic username/email/password account authentication."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response, status
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session as OrmSession

from ..db import get_db
from ..deps import get_current_user, header_session
from ..models import Clip, Session, User
from ..schemas import AuthUserOut, SignInIn, SignUpIn
from ..services.auth_service import (
    end_login,
    hash_password,
    normalize_email,
    normalize_username,
    start_login,
    verify_password,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _out(user: User) -> AuthUserOut:
    return AuthUserOut(
        id=user.id,
        username=user.username,
        email=user.email,
        created_at=user.created_at,
    )


def _conflict(message: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail={"code": "account_exists", "message": message},
    )


@router.post("/signup", response_model=AuthUserOut, status_code=status.HTTP_201_CREATED)
def signup(
    payload: SignUpIn,
    response: Response,
    x_lifeclip_session: str | None = Header(default=None),
    db: OrmSession = Depends(get_db),
):
    username_normalized = normalize_username(payload.username)
    email_normalized = normalize_email(str(payload.email))

    if db.query(User).filter(User.username_normalized == username_normalized).first():
        raise _conflict("That username is already taken.")
    if db.query(User).filter(User.email_normalized == email_normalized).first():
        raise _conflict("An account already uses that email address.")

    user = User(
        username=payload.username.strip(),
        username_normalized=username_normalized,
        email=str(payload.email).strip(),
        email_normalized=email_normalized,
        password_hash=hash_password(payload.password),
    )
    db.add(user)
    db.flush()

    current = header_session(x_lifeclip_session, db, create=True)
    if current is not None and current.user_id is None:
        current.user_id = user.id
    else:
        db.add(Session(user_id=user.id))

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise _conflict("That username or email is already registered.")

    db.refresh(user)
    start_login(response, db, user)
    return _out(user)


@router.post("/login", response_model=AuthUserOut)
def login(
    payload: SignInIn,
    response: Response,
    x_lifeclip_session: str | None = Header(default=None),
    db: OrmSession = Depends(get_db),
):
    identifier = payload.identifier.strip().casefold()
    user = db.query(User).filter(or_(
        User.username_normalized == identifier,
        User.email_normalized == identifier,
    )).one_or_none()

    if not verify_password(payload.password, user.password_hash if user else None):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "invalid_credentials", "message": "Incorrect username/email or password."},
        )
    assert user is not None

    canonical = db.query(Session).filter(Session.user_id == user.id).one_or_none()
    if canonical is None:
        canonical = Session(user_id=user.id)
        db.add(canonical)
        db.flush()

    current = header_session(x_lifeclip_session, db, create=False)
    if current is not None and current.id != canonical.id and current.user_id is None:
        # Preserve pre-login captures by moving them into the account. The
        # canonical account settings remain authoritative.
        db.query(Clip).filter(Clip.session_id == current.id).update(
            {Clip.session_id: canonical.id}, synchronize_session=False
        )
        db.delete(current)

    db.commit()
    start_login(response, db, user)
    return _out(user)


@router.get("/me", response_model=AuthUserOut)
def me(user: User = Depends(get_current_user)):
    return _out(user)


@router.post("/logout")
def logout(
    request: Request,
    response: Response,
    db: OrmSession = Depends(get_db),
):
    end_login(request, response, db)
    return {"signed_out": True}
