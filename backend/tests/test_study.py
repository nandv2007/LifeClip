"""Study tools: summarize / explain / quiz / flashcards — all must be grounded
in the source text (no invented content)."""

from app.services.analysis import study
from app.services.analysis.ocr import extract_text

from .conftest import sample_bytes


def _notes_text() -> str:
    return extract_text(sample_bytes("sample_notes.jpg")).text


def test_summarize_returns_source_sentences():
    text = _notes_text()
    points = study.summarize(text)
    assert points, "expected summary points"
    for p in points:
        # every point must be verbatim from the source (grounded, not generated)
        assert p["point"] in text


def test_quiz_blank_answer_in_source():
    text = _notes_text()
    qs = study.quiz(text)
    assert qs, "expected quiz questions"
    for q in qs:
        assert "_____" in q["question"]
        assert q["answer"].lower() in text.lower()


def test_flashcards_from_term_definitions():
    text = _notes_text()
    cards = study.flashcards(text)
    assert cards, "expected flashcards"
    assert any("Chlorophyll" in c["front"] for c in cards)


def test_explain_mentions_key_terms():
    text = _notes_text()
    items = study.explain(text)
    assert items
    joined = " ".join(i["point"] for i in items).lower()
    assert "photosynthesis" in joined or "key terms" in joined


def test_study_tools_handle_empty_text():
    assert study.summarize("") == []
    assert study.quiz("short") == []
    assert study.flashcards("") == []
