"""End-to-end analysis flow against the REAL analyzer code — the only thing
stubbed is the download URL (a local HTTP server stands in for the Cloudinary
delivery URL, so the exact fetch→OCR→persist code path runs)."""

import functools
import http.server
import threading

import pytest

from app.db import SessionLocal
from app.models import AnalysisRun, Clip
from app.services import analyzer

from .conftest import SAMPLES, make_public_id


@pytest.fixture(scope="module")
def media_server():
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(SAMPLES))
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    port = srv.server_address[1]
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    yield f"http://127.0.0.1:{port}"
    srv.shutdown()


def _make_clip(session_id="analyzer-flow-session") -> str:
    db = SessionLocal()
    from app.models import Session

    if not db.get(Session, session_id):
        db.add(Session(id=session_id))
        db.commit()
    clip = Clip(
        session_id=session_id,
        cloudinary_public_id=make_public_id(),
        secure_url="https://example.invalid/img.jpg",
        format="jpg", width=900, height=1350, byte_size=1000,
        original_filename="poster.jpg", mime_type="image/jpeg", status="uploaded",
    )
    db.add(clip)
    db.commit()
    cid = clip.id
    db.close()
    return cid


class TestAnalysisExecution:
    def test_full_run_persists_result(self, client, media_server, monkeypatch):
        monkeypatch.setattr(
            analyzer, "analysis_url",
            lambda settings, public_id, fmt: f"{media_server}/sample_event_poster.jpg",
        )
        clip_id = _make_clip()
        db = SessionLocal()
        run = AnalysisRun(clip_id=clip_id, attempt=1, status="queued", phase="queued")
        db.add(run)
        db.commit()
        run_id = run.id
        db.close()

        from app.config import get_settings

        analyzer.run_analysis(clip_id, run_id, get_settings())

        db = SessionLocal()
        clip = db.get(Clip, clip_id)
        run = db.get(AnalysisRun, run_id)
        assert clip.status == "ready"
        assert clip.category == "event"
        assert "Conference" in (clip.title or "")
        assert run.status == "succeeded"
        assert any(f.name == "date" for f in clip.fields)
        assert any(a.action_type == "calendar" for a in clip.actions)
        assert clip.raw_text and "October" in clip.raw_text
        db.close()

    def test_failed_fetch_marks_failed_honestly(self, monkeypatch):
        monkeypatch.setattr(
            analyzer, "analysis_url",
            lambda settings, public_id, fmt: "http://127.0.0.1:1/nope.jpg",
        )
        clip_id = _make_clip(session_id="analyzer-flow-session-2")
        db = SessionLocal()
        run = AnalysisRun(clip_id=clip_id, attempt=1, status="queued", phase="queued")
        db.add(run)
        db.commit()
        run_id = run.id
        db.close()

        from app.config import get_settings

        analyzer.run_analysis(clip_id, run_id, get_settings())

        db = SessionLocal()
        clip = db.get(Clip, clip_id)
        assert clip.status == "failed"
        assert clip.analysis_error and "download" in clip.analysis_error.lower()
        db.close()


class TestIdempotency:
    def test_analyze_endpoint_reuses_active_run(self, client):
        """A clip with an active run must NOT get a duplicate run on refresh."""
        session_headers = {"X-Lifeclip-Session": "idempotency-session-00001"}
        clip_id = _make_clip(session_id="idempotency-session-00001")
        db = SessionLocal()
        run = AnalysisRun(clip_id=clip_id, attempt=1, status="running", phase="understanding")
        db.add(run)
        clip = db.get(Clip, clip_id)
        clip.status = "analyzing"
        db.commit()
        n_runs = db.query(AnalysisRun).filter(AnalysisRun.clip_id == clip_id).count()
        db.close()

        r = client.post(f"/api/clips/{clip_id}/analyze", headers=session_headers, json={})
        assert r.status_code == 202
        assert r.json()["run_status"] == "running"

        db = SessionLocal()
        assert db.query(AnalysisRun).filter(AnalysisRun.clip_id == clip_id).count() == n_runs
        db.close()
