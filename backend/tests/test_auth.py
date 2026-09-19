"""Basic account authentication, isolation, and migration coverage."""

import uuid

from app.db import SessionLocal
from app.models import Clip, Session, User

from .conftest import make_public_id


def _identity(prefix: str = "person") -> tuple[str, str]:
    suffix = uuid.uuid4().hex[:10]
    return f"{prefix}_{suffix}", f"{prefix}_{suffix}@example.com"


def test_signup_sets_securely_managed_login_and_never_stores_password(client):
    username, email = _identity("signup")
    token = f"preaccount-{uuid.uuid4().hex}"
    response = client.post(
        "/api/auth/signup",
        headers={"X-Lifeclip-Session": token},
        json={"username": username, "email": email, "password": "correct horse 42"},
    )
    assert response.status_code == 201
    assert response.json()["username"] == username
    assert response.json()["email"] == email
    cookie = response.headers["set-cookie"]
    assert "lifeclip_auth=" in cookie
    assert "HttpOnly" in cookie
    assert "SameSite=lax" in cookie

    assert client.get("/api/auth/me").status_code == 200
    assert client.get("/api/clips", headers={"X-Lifeclip-Session": "ignored-token-123456"}).status_code == 200

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username_normalized == username.casefold()).one()
        assert user.password_hash != "correct horse 42"
        assert "correct horse" not in user.password_hash
        assert user.session.id == token
    finally:
        db.close()


def test_username_and_email_login_are_case_insensitive(client):
    username, email = _identity("login")
    password = "strong-pass-903"
    headers = {"X-Lifeclip-Session": f"signup-{uuid.uuid4().hex}"}
    assert client.post("/api/auth/signup", headers=headers, json={
        "username": username, "email": email, "password": password,
    }).status_code == 201
    assert client.post("/api/auth/logout").status_code == 200

    by_username = client.post("/api/auth/login", headers={
        "X-Lifeclip-Session": f"login-{uuid.uuid4().hex}"
    }, json={"identifier": username.upper(), "password": password})
    assert by_username.status_code == 200
    assert by_username.json()["username"] == username
    assert client.post("/api/auth/logout").status_code == 200

    by_email = client.post("/api/auth/login", headers={
        "X-Lifeclip-Session": f"login-{uuid.uuid4().hex}"
    }, json={"identifier": email.upper(), "password": password})
    assert by_email.status_code == 200


def test_bad_login_is_generic_and_claimed_session_needs_cookie(client):
    username, email = _identity("private")
    token = f"private-{uuid.uuid4().hex}"
    headers = {"X-Lifeclip-Session": token}
    assert client.post("/api/auth/signup", headers=headers, json={
        "username": username, "email": email, "password": "private-pass-33",
    }).status_code == 201
    assert client.post("/api/auth/logout").status_code == 200

    response = client.post("/api/auth/login", headers={
        "X-Lifeclip-Session": f"wrong-{uuid.uuid4().hex}"
    }, json={"identifier": username, "password": "wrong-password"})
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_credentials"

    # The former localStorage token cannot open account data after logout.
    response = client.get("/api/clips", headers=headers)
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "not_authenticated"


def test_login_moves_preaccount_clips_into_existing_account(client):
    username, email = _identity("merge")
    password = "merge-pass-882"
    signup_token = f"signup-{uuid.uuid4().hex}"
    assert client.post("/api/auth/signup", headers={"X-Lifeclip-Session": signup_token}, json={
        "username": username, "email": email, "password": password,
    }).status_code == 201
    assert client.post("/api/auth/logout").status_code == 200

    anonymous_token = f"anonymous-{uuid.uuid4().hex}"
    db = SessionLocal()
    try:
        anonymous = Session(id=anonymous_token)
        db.add(anonymous)
        clip = Clip(
            session_id=anonymous_token,
            cloudinary_public_id=make_public_id(),
            secure_url="https://res.cloudinary.com/demo/image/upload/lifeclip/prelogin.jpg",
            original_filename="before-login.jpg",
            mime_type="image/jpeg",
            status="ready",
            category="notes",
        )
        db.add(clip)
        db.commit()
        clip_id = clip.id
    finally:
        db.close()

    response = client.post("/api/auth/login", headers={
        "X-Lifeclip-Session": anonymous_token
    }, json={"identifier": username, "password": password})
    assert response.status_code == 200
    library = client.get("/api/clips", headers={"X-Lifeclip-Session": anonymous_token})
    assert library.status_code == 200
    assert any(item["id"] == clip_id for item in library.json())

    db = SessionLocal()
    try:
        assert db.get(Session, anonymous_token) is None
    finally:
        db.close()


def test_account_deletion_removes_identity_and_login(client):
    username, email = _identity("delete")
    assert client.post("/api/auth/signup", headers={
        "X-Lifeclip-Session": f"delete-{uuid.uuid4().hex}"
    }, json={
        "username": username, "email": email, "password": "delete-pass-772",
    }).status_code == 201

    deleted = client.delete("/api/account")
    assert deleted.status_code == 200
    assert deleted.json()["deleted"] is True
    assert client.get("/api/auth/me").status_code == 401

    db = SessionLocal()
    try:
        assert db.query(User).filter(User.username_normalized == username.casefold()).first() is None
    finally:
        db.close()


def test_signup_validates_and_rejects_duplicate_identity(client):
    username, email = _identity("duplicate")
    payload = {"username": username, "email": email, "password": "duplicate-pass-1"}
    assert client.post("/api/auth/signup", headers={
        "X-Lifeclip-Session": f"first-{uuid.uuid4().hex}"
    }, json=payload).status_code == 201
    assert client.post("/api/auth/logout").status_code == 200

    duplicate = client.post("/api/auth/signup", headers={
        "X-Lifeclip-Session": f"second-{uuid.uuid4().hex}"
    }, json={**payload, "username": username.upper()})
    assert duplicate.status_code == 409

    invalid = client.post("/api/auth/signup", headers={
        "X-Lifeclip-Session": f"invalid-{uuid.uuid4().hex}"
    }, json={"username": "bad name", "email": "not-an-email", "password": "short"})
    assert invalid.status_code == 422
