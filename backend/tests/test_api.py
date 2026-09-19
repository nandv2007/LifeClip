"""API contract tests: health, sessions, validation, error envelope,
settings, deletion — everything that doesn't need live Cloudinary calls."""

import io

from .conftest import make_public_id


class TestHealth:
    def test_health_ok(self, client):
        r = client.get("/api/health")
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "ok"
        assert body["database"] == "ok"
        assert body["cloudinary_configured"] is False  # no creds in test env
        # security: health output never carries credential material
        assert "secret" not in str(body).lower()


class TestSessions:
    def test_missing_session_rejected_nicely(self, client):
        r = client.get("/api/clips")
        assert r.status_code == 401
        assert r.json()["error"]["code"] == "no_session"

    def test_new_session_starts_with_empty_history(self, client, session_headers):
        r = client.get("/api/clips", headers=session_headers)
        assert r.status_code == 200
        assert r.json() == []


class TestUploadValidation:
    def test_rejects_unsupported_mime(self, client, session_headers):
        r = client.post("/api/upload-signature", headers=session_headers, json={
            "filename": "malware.exe", "mime_type": "application/x-msdownload", "byte_size": 1000,
        })
        assert r.status_code == 415
        assert "JPEG" in r.json()["error"]["message"]

    def test_rejects_pdf_uploads(self, client, session_headers):
        r = client.post("/api/upload-signature", headers=session_headers, json={
            "filename": "notes.pdf", "mime_type": "application/pdf", "byte_size": 1000,
        })
        assert r.status_code == 415
        assert "JPEG" in r.json()["error"]["message"]

    def test_rejects_oversized(self, client, session_headers):
        r = client.post("/api/upload-signature", headers=session_headers, json={
            "filename": "huge.jpg", "mime_type": "image/jpeg", "byte_size": 60 * 1024 * 1024,
        })
        assert r.status_code == 413

    def test_signature_requires_cloudinary_config(self, client, session_headers):
        """Valid request, but no credentials configured -> honest 503."""
        r = client.post("/api/upload-signature", headers=session_headers, json={
            "filename": "poster.jpg", "mime_type": "image/jpeg", "byte_size": 500_000,
        })
        assert r.status_code == 503
        body = r.json()
        assert body["error"]["code"] == "cloudinary_not_configured"
        assert "backend/.env" in body["error"]["message"]

    def test_create_clip_rejected_without_cloudinary(self, client, session_headers):
        r = client.post("/api/clips", headers=session_headers, json={
            "public_id": make_public_id(), "original_filename": "x.jpg", "mime_type": "image/jpeg",
        })
        assert r.status_code == 503

    def test_create_clip_rejects_foreign_public_id(self, client, session_headers):
        r = client.post("/api/clips", headers=session_headers, json={
            "public_id": "someone-else/asset", "original_filename": "x.jpg", "mime_type": "image/jpeg",
        })
        assert r.status_code == 400


class TestNotFound:
    def test_missing_clip(self, client, session_headers):
        r = client.get("/api/clips/does-not-exist", headers=session_headers)
        assert r.status_code == 404
        assert r.json()["error"]["code"] == "not_found"

    def test_missing_action(self, client, session_headers):
        r = client.post("/api/actions/nope/confirm", headers=session_headers, json={"payload": {}})
        assert r.status_code == 404


class TestValidationEnvelope:
    def test_bad_body_is_friendly(self, client, session_headers):
        r = client.post("/api/upload-signature", headers=session_headers, json={"nope": 1})
        assert r.status_code == 422
        body = r.json()
        assert body["error"]["code"] == "invalid_request"
        assert "invalid" in body["error"]["message"].lower()


class TestSettings:
    def test_settings_roundtrip(self, client, session_headers):
        r = client.get("/api/settings", headers=session_headers)
        assert r.status_code == 200
        assert r.json()["retention_days"] == 90

        r = client.patch("/api/settings", headers=session_headers,
                         json={"retention_days": 30, "save_extracted_text": False})
        assert r.status_code == 200
        assert r.json()["retention_days"] == 30
        assert r.json()["save_extracted_text"] is False

    def test_delete_account_clears_session(self, client):
        headers = {"X-Lifeclip-Session": "temp-session-to-delete-01"}
        assert client.get("/api/clips", headers=headers).status_code == 200
        r = client.delete("/api/account", headers=headers)
        assert r.status_code == 200
        assert r.json()["deleted"] is True


class TestSecurityHeaders:
    def test_headers_present(self, client):
        r = client.get("/api/health")
        assert r.headers["X-Content-Type-Options"] == "nosniff"
        assert "camera=(self)" in r.headers["Permissions-Policy"]

    def test_api_key_secret_never_in_openapi(self, client):
        spec = client.get("/api/openapi.json").text
        assert "api_secret" not in spec
