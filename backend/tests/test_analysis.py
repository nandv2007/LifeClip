"""Verify the analysis pipeline against the 8 required test media types,
plus adversarial (prompt-injection) input."""

from app.services.analysis.pipeline import run_pipeline

from .conftest import sample_bytes


def _run(name):
    return run_pipeline(sample_bytes(name))


def _field(result, name):
    for f in result.fields:
        if f.name == name:
            return f
    return None


class TestCategories:
    def test_event_poster(self):
        r = _run("sample_event_poster.jpg")
        assert r.category == "event"
        assert "Conference" in r.title
        assert _field(r, "date") and "25" in _field(r, "date").value
        assert _field(r, "time") and "10:00" in _field(r, "time").value
        assert _field(r, "location") and "Chennai Trade Centre" in _field(r, "location").value
        types = [a.action_type for a in r.actions]
        assert "calendar" in types and "reminder" in types and "directions" in types
        # 2-5 primaries
        assert 2 <= len([a for a in r.actions if a.primary]) <= 5

    def test_receipt(self):
        r = _run("sample_receipt.jpg")
        assert r.category == "receipt"
        assert r.title.startswith("ANNA NAGAR MART")
        assert _field(r, "total") and _field(r, "total").value == "1496.78"
        assert _field(r, "currency") and _field(r, "currency").value == "INR"
        assert _field(r, "items")
        assert _field(r, "date") and "14/09/2026" in _field(r, "date").value
        types = [a.action_type for a in r.actions]
        assert "expense" in types and "save" in types

    def test_ticket(self):
        r = _run("sample_ticket.jpg")
        assert r.category == "ticket"
        assert _field(r, "seat") and "14A" in _field(r, "seat").value
        assert _field(r, "date") and "November" in _field(r, "date").value
        ref = _field(r, "reference")
        assert ref and ref.value == "KX7P2Q"
        types = [a.action_type for a in r.actions]
        assert "calendar" in types and "save" in types

    def test_notes(self):
        r = _run("sample_notes.jpg")
        assert r.category == "notes"
        assert "Photosynthesis" in r.title
        assert len(r.text.split()) > 40
        types = [a.action_type for a in r.actions]
        assert "summarize" in types and "quiz" in types and "flashcards" in types

    def test_menu(self):
        r = _run("sample_menu.jpg")
        assert r.category == "menu"
        dishes = _field(r, "dishes")
        assert dishes and "Biryani" in dishes.value
        types = [a.action_type for a in r.actions]
        assert "translate" in types

    def test_product(self):
        r = _run("sample_product.jpg")
        assert r.category == "product"
        assert "NovaBuds" in r.title
        assert _field(r, "model") and "NB-410X" in _field(r, "model").value
        assert _field(r, "warranty") and "1 year" in _field(r, "warranty").value
        types = [a.action_type for a in r.actions]
        assert "warranty" in types and "search" in types

    def test_notice(self):
        r = _run("sample_notice.jpg")
        assert r.category == "document"
        assert "Water Tank" in r.title
        assert _field(r, "deadline") and "28 September 2026" in _field(r, "deadline").value
        assert _field(r, "email")
        types = [a.action_type for a in r.actions]
        assert "summarize" in types and "reminder" in types

    def test_unknown_image_graceful_fallback(self):
        r = _run("sample_unknown.jpg")
        assert r.category == "other"
        # Never an empty result:
        assert len(r.actions) >= 2
        types = [a.action_type for a in r.actions]
        assert "save" in types and "open_original" in types


class TestHonesty:
    def test_never_invents_missing_fields(self):
        """Unknown image has no date — pipeline must not fabricate one."""
        r = _run("sample_unknown.jpg")
        assert _field(r, "date") is None
        assert _field(r, "total") is None

    def test_confidence_is_bounded(self):
        r = _run("sample_event_poster.jpg")
        for f in r.fields:
            assert 0.0 < f.confidence <= 1.0

    def test_ambiguous_numeric_date_warns(self):
        """02/03 style dates must be flagged, not silently interpreted."""
        from app.services.analysis.extract import find_dates

        fields, warnings = find_dates("Meeting on 02/03/26 at noon", 0.9)
        assert fields and any("ambiguous" in w.lower() for w in warnings)


class TestPromptInjection:
    def test_injected_instructions_are_inert(self):
        r = _run("sample_injection.jpg")
        # The attack text is surfaced as a warning; confidences are dampened.
        assert any("instructions" in w.lower() or "misleading" in w.lower() for w in r.warnings)
        assert r.category_confidence <= 0.5
        # No URL pointing at the attacker's domain may be emitted as a link field.
        for f in r.fields:
            assert "evil.example.com" not in f.value

    def test_sanitization_strips_control_and_bidi(self):
        from app.services.analysis.pipeline import sanitize_untrusted

        dirty = "hello\u202e world\x00 evil"
        clean = sanitize_untrusted(dirty, 1000)
        assert "\u202e" not in clean and "\x00" not in clean
