"""Smart-library metadata and global-search API coverage."""

import json

from app.db import SessionLocal
from app.models import Clip, ExtractedField, Session

from .conftest import make_public_id


def _library_clip(session_id: str) -> str:
    db = SessionLocal()
    if not db.get(Session, session_id):
        db.add(Session(id=session_id))
        db.commit()
    clip = Clip(
        session_id=session_id,
        cloudinary_public_id=make_public_id(),
        secure_url="https://res.cloudinary.com/demo/image/upload/lifeclip/search.jpg",
        format="jpg",
        width=1200,
        height=1600,
        byte_size=45_000,
        original_filename="thermodynamics-week-4.jpg",
        mime_type="image/jpeg",
        status="ready",
        category="notes",
        title="Energy and Entropy",
        raw_text="The second law discusses entropy in an isolated system.",
        subject="Physics",
        topic="Thermodynamics",
        tags_json=json.dumps(["semester 2", "revision"]),
        headings_json=json.dumps(["Second law"]),
        concepts_json=json.dumps(["Entropy"]),
        extracted_text_status="ocr",
        ocr_used=True,
        analysis_confidence=0.91,
    )
    db.add(clip)
    db.commit()
    db.add(ExtractedField(
        clip_id=clip.id,
        name="concepts",
        label="Key concepts",
        value="Entropy, closed system, heat transfer",
        confidence=0.8,
        position=0,
    ))
    db.commit()
    clip_id = clip.id
    db.close()
    return clip_id


def test_global_search_covers_filename_tags_subject_topic_and_fields(client):
    session_id = "smart-search-session-0001"
    clip_id = _library_clip(session_id)
    headers = {"X-Lifeclip-Session": session_id}
    for query in ["week-4", "semester 2", "Physics", "Thermodynamics", "heat transfer", "entropy"]:
        response = client.get("/api/clips", headers=headers, params={"q": query})
        assert response.status_code == 200
        assert any(item["id"] == clip_id for item in response.json()), query

    response = client.get("/api/clips", headers=headers)
    assert response.status_code == 200
    item = next(item for item in response.json() if item["id"] == clip_id)
    assert item["tags"] == ["semester 2", "revision"]


def test_document_organization_patch_roundtrip(client):
    session_id = "smart-patch-session-0001"
    clip_id = _library_clip(session_id)
    headers = {"X-Lifeclip-Session": session_id}
    response = client.patch(f"/api/clips/{clip_id}", headers=headers, json={
        "category": "document",
        "subject": "Engineering",
        "topic": "Heat engines",
        "tags": [" final exam ", "Final Exam", "week 4"],
    })
    assert response.status_code == 200
    body = response.json()
    assert body["category"] == "document"
    assert body["subject"] == "Engineering"
    assert body["topic"] == "Heat engines"
    assert body["tags"] == ["final exam", "week 4"]
