"""Lenient, honest parsing of dates/times from user-edited payloads.
Never invents values: unparsable input -> None -> the UI asks the user."""

from __future__ import annotations

import re
from datetime import date, time

DATE_FORMATS = (
    "%Y-%m-%d",          # ISO from <input type=date>
    "%d %B %Y", "%d %b %Y",
    "%B %d, %Y", "%b %d, %Y", "%B %d %Y", "%b %d %Y",
    "%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y",
    "%d %B", "%d %b",    # yearless (calendar UI supplies the year separately)
)

TIME_FORMATS = ("%H:%M", "%I:%M %p", "%I %p", "%H.%M")


def parse_date(value: str) -> date | None:
    value = value.strip()
    if not value:
        return None
    for fmt in DATE_FORMATS:
        try:
            from datetime import datetime

            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    return None


def parse_time(value: str) -> time | None:
    value = re.sub(r"\s+", " ", value.strip().upper().replace(".", ":"))
    if not value:
        return None
    value = value.replace("::", ":")
    for fmt in TIME_FORMATS:
        try:
            from datetime import datetime

            return datetime.strptime(value, fmt).time()
        except ValueError:
            continue
    m = re.match(r"^(\d{1,2}):(\d{2})\s*(AM|PM)$", value)
    if m:
        h = int(m.group(1)) % 12 + (12 if m.group(3) == "PM" else 0)
        return time(h, int(m.group(2)))
    return None
