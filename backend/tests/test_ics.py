"""Real iCalendar output for calendar/reminder actions."""

from datetime import datetime, timezone

from app.services.datetime_parse import parse_date, parse_time
from app.services.ics import build_event_ics, safe_filename


def test_ics_contains_event_fields():
    ics = build_event_ics(
        title="AI & Cloud Conference 2026",
        start=datetime(2026, 10, 25, 4, 30, tzinfo=timezone.utc),  # 10:00 IST
        location="Chennai Trade Centre",
        description="Created with LifeClip",
        reminder_minutes=60,
    )
    assert "BEGIN:VCALENDAR" in ics and "END:VCALENDAR" in ics
    assert "SUMMARY:AI & Cloud Conference 2026" in ics
    assert "LOCATION:Chennai Trade Centre" in ics
    assert "DTSTART:20261025T043000Z" in ics
    assert "BEGIN:VALARM" in ics and "TRIGGER:-PT60M" in ics


def test_ics_escapes_special_characters():
    ics = build_event_ics(title="Party; dinner, at 7\nsharp", start=datetime(2026, 1, 1))
    assert "SUMMARY:Party\\; dinner\\, at 7\\nsharp" in ics


def test_datetime_parsing_common_formats():
    assert parse_date("25 October 2026").isoformat() == "2026-10-25"
    assert parse_date("2026-10-25").isoformat() == "2026-10-25"
    assert parse_date("October 25, 2026").isoformat() == "2026-10-25"
    assert parse_date("14/09/2026").isoformat() == "2026-09-14"
    assert parse_date("not a date") is None
    assert parse_time("10:00 AM").hour == 10
    assert parse_time("7:45 AM").hour == 7
    assert parse_time("18:30").hour == 18
    assert parse_time("nonsense") is None


def test_safe_filename():
    assert safe_filename("My Event: 2026?").endswith(".ics")
    assert "/" not in safe_filename("a/b")
