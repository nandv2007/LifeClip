"""Test fixtures. An isolated SQLite file is used per test session; env vars
are set BEFORE app modules are imported (config is cached)."""

import os
import tempfile
import uuid
from pathlib import Path

_TMP = tempfile.mkdtemp(prefix="lifeclip-test-")
# Point DATABASE_URL at PostgreSQL to run the whole suite against it:
#   DATABASE_URL=postgresql+psycopg://lifeclip:lifeclip@localhost:5432/lifeclip_test pytest
os.environ.setdefault("DATABASE_URL", f"sqlite:///{_TMP}/test.db")
os.environ["CLOUDINARY_CLOUD_NAME"] = ""
os.environ["CLOUDINARY_API_KEY"] = ""
os.environ["CLOUDINARY_API_SECRET"] = ""

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

SAMPLES = Path(__file__).resolve().parent.parent.parent / "samples"


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def session_headers():
    return {"X-Lifeclip-Session": "test-session-token-0001"}


def sample_bytes(name: str) -> bytes:
    return (SAMPLES / name).read_bytes()


def make_public_id() -> str:
    """Every test clip MUST get its own public_id — the database enforces
    uniqueness on clips.cloudinary_public_id, and that constraint is a
    strictness we want, not a bug to bypass."""
    return f"lifeclip/test-{uuid.uuid4().hex}"
