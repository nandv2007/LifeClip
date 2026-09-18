"""Generate real iCalendar (.ics) files for confirmed calendar/reminder actions.

Standard RFC 5545 output; works with Google Calendar, Apple Calendar, Outlook
("Add to calendar" = download a .ics the OS/calendar app opens natively).
"""

from __future__ import annotations

import html
import uuid
from datetime import datetime, timedelta, timezone


def _esc(text: str) -> str:
    return (
        text.replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\n", "\\n")
    )


def _fold(line: str) -> str:
    """Fold lines at 75 octets per RFC 5545 (approximation by chars is fine for
    our ASCII-heavy content)."""
    if len(line) <= 74:
        return line
    parts = []
    while len(line) > 74:
        parts.append(line[:74])
        line = " " + line[74:]
    parts.append(line)
    return "\r\n".join(parts)


def build_event_ics(
    title: str,
    start: datetime,
    end: datetime | None = None,
    location: str = "",
    description: str = "",
    reminder_minutes: int | None = None,
) -> str:
    if start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)
    if end is None:
        end = start + timedelta(hours=1)
    if end.tzinfo is None:
        end = end.replace(tzinfo=timezone.utc)

    def fmt(dt: datetime) -> str:
        return dt.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//LifeClip//EN",
        "CALSCALE:GREGORIAN",
        "BEGIN:VEVENT",
        f"UID:{uuid.uuid4().hex}@lifeclip",
        f"DTSTAMP:{fmt(datetime.now(timezone.utc))}",
        f"DTSTART:{fmt(start)}",
        f"DTEND:{fmt(end)}",
        _fold(f"SUMMARY:{_esc(title)}"),
    ]
    if location:
        lines.append(_fold(f"LOCATION:{_esc(location)}"))
    if description:
        lines.append(_fold(f"DESCRIPTION:{_esc(description)}"))
    if reminder_minutes is not None and reminder_minutes >= 0:
        lines += [
            "BEGIN:VALARM",
            f"TRIGGER:-PT{reminder_minutes}M",
            "ACTION:DISPLAY",
            _fold(f"DESCRIPTION:{_esc(title)}"),
            "END:VALARM",
        ]
    lines += ["END:VEVENT", "END:VCALENDAR"]
    return "\r\n".join(lines) + "\r\n"


def safe_filename(title: str) -> str:
    base = "".join(c for c in title if c.isalnum() or c in " -_").strip()[:60]
    return (html.escape(base) or "lifeclip-event") + ".ics"
