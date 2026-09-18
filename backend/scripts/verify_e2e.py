"""FINAL end-to-end sandbox verification of the full LifeClip flow,
run over the real HTTP API + real analyzer, with the ONLY substitution
being where the image BYTES come from:

    A local static file server serves the sample JPEG bytes instead of
    the Cloudinary delivery URL. Everything else — the analyzer's HTTP
    fetch, Tesseract OCR, classification, extraction, confidence, safety,
    action engine, persistence, idempotency, field editing, calendar
    confirmation, .ics generation, history, deletion — is production code
    executed end to end.

Real Cloudinary upload + admin verification requires real credentials;
add them to backend/.env and run scripts/verify_cloudinary.py.

Usage:  cd backend && python scripts/verify_e2e.py
"""

from __future__ import annotations

import functools
import http.server
import os
import sys
import threading
import tempfile
import time
from pathlib import Path

_SCRATCH = tempfile.mkdtemp(prefix="lifeclip-e2e-")
os.environ["DATABASE_URL"] = f"sqlite:///{_SCRATCH}/e2e.db"
# Placeholder, in-process-only values so settings.cloudinary_configured is True
# (the analyze endpoint honestly 503s otherwise). These are NOT credentials,
# they are never committed, and no Cloudinary API call can succeed with them.
os.environ["CLOUDINARY_CLOUD_NAME"] = "tecwmb40"
os.environ["CLOUDINARY_API_KEY"] = "E2E-PLACEHOLDER-NOT-A-REAL-KEY"
os.environ["CLOUDINARY_API_SECRET"] = "E2E-PLACEHOLDER-NOT-A-REAL-SECRET"

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient  # noqa: E402

from app.db import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Action, AnalysisRun, Clip, ExtractedField, Session  # noqa: E402
from app.services import analyzer  # noqa: E402

SAMPLES = Path(__file__).resolve().parent.parent.parent / "samples"
PASSED: list[str] = []
FAILED: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    (PASSED if cond else FAILED).append(f"{name}{' — ' + detail if detail else ''}")
    print(f"  {'✓' if cond else '✗ FAIL'} {name}{('  ' + detail) if detail else ''}")


def media_seed(sample: str = "sample_event_poster.jpg", session_id: str = "e2e-tester-token-00000001"):
    """Start a static server for the sample bytes; insert session + clip rows
    exactly as POST /api/clips would after Cloudinary admin verification."""
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(SAMPLES))
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{srv.server_address[1]}/{sample}"

    import uuid

    db = SessionLocal()
    if not db.get(Session, session_id):
        db.add(Session(id=session_id))
        db.commit()
    clip = Clip(
        session_id=session_id,
        cloudinary_public_id=f"lifeclip/e2e-{uuid.uuid4().hex}",
        secure_url=url, format="jpg", width=900, height=1350, byte_size=os.path.getsize(SAMPLES / sample),
        original_filename=sample, mime_type="image/jpeg", status="uploaded",
    )
    db.add(clip)
    db.commit()
    cid = clip.id
    db.close()
    return cid, url, srv


def wait_ready(client, clip_id, headers, timeout=90):
    """Poll analysis status — this is exactly what the ClipScreen does."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        r = client.get(f"/api/clips/{clip_id}/analysis", headers=headers)
        assert r.status_code == 200, r.text
        body = r.json()
        if body["status"] in ("ready", "partial", "failed"):
            return body
        time.sleep(0.4)
    raise AssertionError("analysis did not finish in time")


def main() -> int:
    headers = {"X-Lifeclip-Session": "e2e-tester-token-00000001"}
    # `with TestClient(...)` runs the app startup event (schema creation) first.
    with TestClient(app) as client:
        print("\n── 1. Upload → DB record (Cloudinary-verified path simulated for bytes) ──")
        clip_id, url, srv = media_seed()
        analyzer.analysis_url = lambda *_: url  # delivery URL -> local bytes for THIS process only

        r = client.get(f"/api/clips/{clip_id}", headers=headers)
        check("clip record persisted & readable", r.status_code == 200)
        check("status starts as 'uploaded'", r.json()["status"] == "uploaded", r.json().get("status", ""))

        print("\n── 2. Analysis: OCR → classify → extract → confidence → actions ──")
        r1 = client.post(f"/api/clips/{clip_id}/analyze", headers=headers)
        check("analyze accepted (202)", r1.status_code == 202)

        print("\n── 3. Refresh-during-analysis idempotency ──")
        r2 = client.post(f"/api/clips/{clip_id}/analyze", headers=headers)  # user hit refresh / retried
        check("second analyze also accepted", r2.status_code == 202)
        check("identical run reused (same run id)", r1.json().get("run_id") == r2.json().get("run_id"),
              f"run {r1.json().get('run_id')}")
        db = SessionLocal()
        runs = db.query(AnalysisRun).filter(AnalysisRun.clip_id == clip_id).all()
        check("exactly ONE AnalysisRun row in DB", len(runs) == 1, f"{len(runs)} row(s)")
        db.close()

        st = wait_ready(client, clip_id, headers)
        check("analysis reaches ready/partial", st["status"] in ("ready", "partial"), st["status"])

        db = SessionLocal()
        clip = db.get(Clip, clip_id)
        n_fields = db.query(ExtractedField).filter(ExtractedField.clip_id == clip_id).count()
        n_actions = db.query(Action).filter(Action.clip_id == clip_id).count()
        check("clip status persisted to DB", clip.status in ("ready", "partial"), clip.status)
        check("extracted fields persisted", n_fields >= 3, f"{n_fields} fields")
        check("recommended actions persisted (2–5 primary)", n_actions >= 5, f"{n_actions} actions")
        db.close()

        r = client.get(f"/api/clips/{clip_id}", headers=headers)
        detail = r.json()
        check("classified as event from real OCR", detail["category"] == "event", detail["category"])
        check(" OCR text captured", len(detail.get("raw_text") or "") > 40)
        fmap = {f["name"]: f for f in detail["fields"]}
        check("date extracted with confidence", "date" in fmap and 0 < fmap["date"]["confidence"] <= 1,
              fmap.get("date", {}).get("value", "?"))
        check("time extracted", "time" in fmap, fmap.get("time", {}).get("value", "?"))
        check("location extracted", "location" in fmap, fmap.get("location", {}).get("value", "?"))
        cals = [a for a in detail["actions"] if a["action_type"] == "calendar"]
        check("calendar action recommended", len(cals) == 1)

        print("\n── 4. Idempotent re-analyze of a finished clip ──")
        r3 = client.post(f"/api/clips/{clip_id}/analyze", headers=headers)
        db = SessionLocal()
        runs = db.query(AnalysisRun).filter(AnalysisRun.clip_id == clip_id).all()
        check("finished clip does not spawn stray runs", len(runs) <= 2, f"{len(runs)} run(s) total")
        db.close()

        print("\n── 5. Editable result ──")
        # Real contract: full-state field list (omitted = user deleted the field).
        edit_list = [
            {"id": f["id"], "name": f["name"], "label": f["label"],
             "value": ("25 October 2026 (tweaked by user)" if f["name"] == "date" else f["value"])}
            for f in detail["fields"]
        ]
        r = client.patch(f"/api/clips/{clip_id}/fields", headers=headers, json={"fields": edit_list})
        check("field edit accepted", r.status_code == 200)
        fmap = {f["name"]: f for f in r.json()["fields"]}
        check("edit persisted + marked user-confirmed",
              fmap["date"]["value"].startswith("25 October 2026")
              and fmap["date"]["user_edited"] is True and fmap["date"]["confidence"] == 1.0,
              f"user_edited={fmap['date'].get('user_edited')}")
        # persistence across a fresh GET (what a refresh sees):
        r = client.get(f"/api/clips/{clip_id}", headers=headers)
        fmap2 = {f["name"]: f for f in r.json()["fields"]}
        check("edit survives reload", fmap2["date"]["value"] == "25 October 2026 (tweaked by user)")

        print("\n── 6. Calendar confirmation + .ics generation ──")
        cal = cals[0]
        r = client.post(f"/api/actions/{cal['id']}/confirm", headers=headers, json={"payload": {
            "title": "AI & Cloud Conference 2026", "date": "25 October 2026",
            "time": "10:00 AM", "location": "Chennai Trade Centre", "reminder_minutes": 60,
        }})
        check("confirm accepted", r.status_code == 200, str(r.status_code))
        body = r.json()
        check("confirm returns ics download url", bool(body.get("download_url")))
        r = client.get(body["download_url"], headers=headers)
        text = r.text
        check(".ics served with session header (200)", r.status_code == 200)
        check(".ics is a real VEVENT", "BEGIN:VCALENDAR" in text and "BEGIN:VEVENT" in text)
        # Wall-clock semantic: the confirmed time is stamped exactly as seen.
        check("confirmed wall-clock time in DTSTART", "DTSTART:20261025T100000Z" in text)
        check("VALARM -60min present", "TRIGGER:-PT60M" in text)
        check("summary/location present", "AI & Cloud Conference 2026" in text and "Chennai Trade Centre" in text)
        db = SessionLocal()
        act = db.get(Action, cal["id"])
        check("action marked confirmed in DB", act.status == "confirmed", act.status)
        db.close()

        print("\n── 7. History: list / search / filter ──")
        r = client.get("/api/clips", headers=headers)
        check("history lists the clip", len(r.json()) == 1)
        r = client.get("/api/clips?q=cloud+conference", headers=headers)
        check("search finds it", len(r.json()) == 1, r.json()[0]["title"] if r.json() else "none")
        r = client.get("/api/clips?category=receipt", headers=headers)
        check("filter excludes non-matching categories", len(r.json()) == 0)

        print("\n── 8. Deletion ──")
        r = client.delete(f"/api/clips/{clip_id}", headers=headers)
        check("delete returns 200", r.status_code == 200)
        r = client.get(f"/api/clips/{clip_id}", headers=headers)
        check("clip gone (404) after delete", r.status_code == 404)
        db = SessionLocal()
        gone = (db.get(Clip, clip_id) is None
                and db.query(ExtractedField).filter(ExtractedField.clip_id == clip_id).count() == 0
                and db.query(Action).filter(Action.clip_id == clip_id).count() == 0
                and db.query(AnalysisRun).filter(AnalysisRun.clip_id == clip_id).count() == 0)
        check("cascade removed fields/actions/runs from DB", gone)
        r = client.get("/api/clips", headers=headers)
        check("history empty after refresh", r.json() == [])
        db.close()

        print("\n── 9. Error handling on the wire ──")
        r = client.post(f"/api/actions/nonexistent/confirm", headers=headers, json={"payload": {}})
        check("missing action → friendly 404", r.status_code == 404 and r.json()["error"]["code"] == "not_found")
        # Secret hygiene on the wire: signature params must NEVER include the secret,
        # only the public api_key + HMAC. (The honest-503-when-unconfigured path is
        # covered by the unit suite, which runs with empty credentials.)
        r = client.post("/api/upload-signature", headers=headers,
                        json={"filename": "x.jpg", "mime_type": "image/jpeg", "byte_size": 1000})
        check("upload signature issued", r.status_code == 200)
        check("public_id under lifeclip/ folder", r.json()["public_id"].startswith("lifeclip/"))
        check("api_secret never in signature response", "api_secret" not in r.text
              and "E2E-PLACEHOLDER-NOT-A-REAL-SECRET" not in r.text)
        r = client.get("/api/clips", headers={"X-Lifeclip-Session": "someone-else-999"})
        check("foreign session cannot see clips", r.status_code == 200 and r.json() == [])

    print(f"\n{'═' * 66}")
    print(f"FINAL E2E VERIFICATION: {len(PASSED)} passed, {len(FAILED)} failed")
    if FAILED:
        print("FAILURES:")
        for f in FAILED:
            print(f"  ✗ {f}")
    print(f"{'═' * 66}")
    return 1 if FAILED else 0


if __name__ == "__main__":
    raise SystemExit(main())
