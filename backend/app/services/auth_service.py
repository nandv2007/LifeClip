"""Password hashing and revocable cookie-session helpers.

Raw passwords and raw login tokens are never stored. Passwords use Argon2id;
login tokens are random 256-bit values represented only by SHA-256 digests in
the database.
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from fastapi import Request, Response
from sqlalchemy.orm import Session as OrmSession

from ..config import get_settings
from ..models import AuthSession, User, utcnow

_PASSWORD_HASHER = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=2)
# Used when an identifier is unknown so failed-login timing remains comparable.
_DUMMY_HASH = _PASSWORD_HASHER.hash("lifeclip-invalid-password")


def normalize_username(value: str) -> str:
    return value.strip().casefold()


def normalize_email(value: str) -> str:
    return value.strip().casefold()


def hash_password(password: str) -> str:
    return _PASSWORD_HASHER.hash(password)


def verify_password(password: str, encoded: str | None) -> bool:
    candidate = encoded or _DUMMY_HASH
    try:
        valid = _PASSWORD_HASHER.verify(candidate, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False
    return bool(valid and encoded)


def token_digest(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


def authenticated_session(request: Request, db: OrmSession) -> AuthSession | None:
    settings = get_settings()
    raw_token = request.cookies.get(settings.auth_cookie_name, "")
    if not raw_token or len(raw_token) > 256:
        return None
    login = (
        db.query(AuthSession)
        .filter(AuthSession.token_hash == token_digest(raw_token))
        .one_or_none()
    )
    if login is None:
        return None
    if _aware(login.expires_at) <= utcnow():
        db.delete(login)
        db.commit()
        return None
    login.last_seen_at = utcnow()
    db.commit()
    return login


def start_login(response: Response, db: OrmSession, user: User) -> None:
    settings = get_settings()
    raw_token = secrets.token_urlsafe(32)
    max_age = max(1, settings.auth_session_days) * 24 * 60 * 60
    db.add(AuthSession(
        user_id=user.id,
        token_hash=token_digest(raw_token),
        expires_at=utcnow() + timedelta(seconds=max_age),
    ))
    db.commit()
    response.set_cookie(
        key=settings.auth_cookie_name,
        value=raw_token,
        max_age=max_age,
        expires=max_age,
        path="/",
        secure=settings.secure_auth_cookie,
        httponly=True,
        samesite="lax",
    )


def end_login(request: Request, response: Response, db: OrmSession) -> None:
    settings = get_settings()
    raw_token = request.cookies.get(settings.auth_cookie_name, "")
    if raw_token:
        db.query(AuthSession).filter(
            AuthSession.token_hash == token_digest(raw_token)
        ).delete(synchronize_session=False)
        db.commit()
    response.delete_cookie(
        key=settings.auth_cookie_name,
        path="/",
        secure=settings.secure_auth_cookie,
        httponly=True,
        samesite="lax",
    )
