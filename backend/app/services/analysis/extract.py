"""Structured information extraction per category.

HARD RULES (hallucination control):
  * A field is only emitted when a real pattern matched the OCR text.
  * Missing information is reported as "Not detected" — never guessed.
  * Ambiguous values (e.g. 02/03/26 — which is the month?) keep their literal
    text and carry a low confidence plus a warning asking the user to confirm.
  * OCR text is treated as UNTRUSTED data: it is never interpreted as
    instructions anywhere in this pipeline.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field as dc_field

# ---------------------------------------------------------------- primitives

MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6, "jul": 7,
    "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}
MONTH_NAMES = {v: k.capitalize() for k, v in MONTHS.items()}
MONTH_FULL = {
    1: "January", 2: "February", 3: "March", 4: "April", 5: "May", 6: "June",
    7: "July", 8: "August", 9: "September", 10: "October", 11: "November",
    12: "December",
}
RE_TOTAL_WORD = re.compile(r"\b(grand\s*total|total|amount due|balance|subtotal)\b", re.IGNORECASE)

RE_DATE_NUMERIC = re.compile(r"\b(\d{1,2})[/-](\d{1,2})(?:[/-](\d{2,4}))?\b")
RE_DATE_DAY_FIRST = re.compile(
    r"\b(\d{1,2})(?:st|nd|rd|th)?[ \t]+(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)"
    r"[a-z]*(?:[,]?[ \t]+(\d{4}))?\b", re.IGNORECASE)
RE_DATE_MONTH_FIRST = re.compile(
    r"\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*[ \t]+(\d{1,2})"
    r"(?:st|nd|rd|th)?(?:[,]?[ \t]+(\d{4}))?\b", re.IGNORECASE)
RE_TIME = re.compile(r"\b(\d{1,2})[:.](\d{2})\s*(am|pm|AM|PM)?\b|\b(\d{1,2})\s*(am|pm|AM|PM)\b")
RE_MONEY = re.compile(
    r"(?P<cur>[$€£₹]|Rs\.?|INR|USD|EUR|GBP)?\s*(?P<amt>(?:\d{1,3}(?:,\d{2,3})+|\d+)(?:\.\d{1,2})?)")
RE_URL = re.compile(r"(?:https?://)?(?:www\.)?[a-zA-Z0-9-]+(?:\.[a-zA-Z]{2,})+(?:/[^\s]*)?", re.IGNORECASE)
RE_EMAIL = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.]{2,}\b")
RE_PHONE = re.compile(r"(?:\+\d{1,3}[\s-]?)?(?:\(?\d{3,5}\)?[\s-]?)?\d{3,5}[\s-]\d{4}|\+?\d[\d\s-]{8,14}\d")
RE_SEAT = re.compile(r"\bseat\s*(?:no\.?|number|#)?\s*:?\s*([A-Z0-9-]{1,6})\b|\b(?:row)\s+([A-Z0-9]{1,4})\b", re.IGNORECASE)
RE_PNR = re.compile(r"\bpnr\s*(?:no\.?|number|#)?\s*:?\s*([A-Z0-9]{5,10})\b", re.IGNORECASE)
RE_BOOKING_REF = re.compile(
    r"\b(?:booking\s*(?:reference|ref)|order\s*(?:id|#|no\.?)|confirmation|reference|ref(?:erence)?)"
    r"\s*(?:no\.?|#|:|:)?\s*(?=[A-Z0-9-]*\d)([A-Z0-9-]{5,18})\b",
    re.IGNORECASE)
RE_MODEL = re.compile(r"\bmodel\s*(?:no\.?|name|#)?\s*:?\s*([A-Za-z0-9][A-Za-z0-9 -]{1,24})\b", re.IGNORECASE)

CUR_SYMBOLS = {"$": "USD", "€": "EUR", "£": "GBP", "₹": "INR"}


def _norm_cur(cur: str) -> str:
    c = cur.strip().rstrip(".").upper()
    if c in ("RS", "INR"):
        return "INR"
    return c


@dataclass
class Field:
    name: str
    label: str
    value: str
    confidence: float


@dataclass
class Extraction:
    title: str
    title_confidence: float
    fields: list[Field]
    warnings: list[str] = dc_field(default_factory=list)


def _clean(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip(" \t,;:|-–—")


def _num(s: str) -> str:
    return s.replace(",", "")


# ------------------------------------------------------------------ dates


def find_dates(text: str, ocr_conf: float) -> tuple[list[Field], list[str]]:
    fields: list[Field] = []
    warnings: list[str] = []
    seen: set[str] = set()

    def push(value: str, conf: float, norm: str | None, extra_warn: str | None = None):
        key = norm or value.lower()
        if key in seen or len(fields) >= 3:
            return
        seen.add(key)
        fields.append(Field("date", "Date", value, conf))
        if extra_warn:
            warnings.append(extra_warn)

    for m in RE_DATE_DAY_FIRST.finditer(text):
        day, mon, year = m.group(1), MONTHS[m.group(2)[:3].lower()], m.group(3)
        norm = f"{year or '????'}-{mon:02d}-{int(day):02d}"
        value = f"{int(day)} {MONTH_FULL[mon]}" + (f" {year}" if year else "")
        conf = 0.85 if year else 0.7
        warn = None if year else "The year was not visible on the date — please confirm it."
        push(_clean(value), round(conf * max(ocr_conf, 0.5), 2), norm, warn)

    for m in RE_DATE_MONTH_FIRST.finditer(text):
        mon, day, year = MONTHS[m.group(1)[:3].lower()], m.group(2), m.group(3)
        norm = f"{year or '????'}-{mon:02d}-{int(day):02d}"
        value = f"{int(day)} {MONTH_FULL[mon]}" + (f" {year}" if year else "")
        conf = 0.85 if year else 0.7
        warn = None if year else "The year was not visible on the date — please confirm it."
        push(_clean(value), round(conf * max(ocr_conf, 0.5), 2), norm, warn)

    for m in RE_DATE_NUMERIC.finditer(text):
        d1, d2, year = int(m.group(1)), int(m.group(2)), m.group(3)
        if d1 > 31 or d2 > 31 or (d1 <= 12 and d2 > 31):
            continue  # not a date at all
        ambiguous = d1 <= 12 and d2 <= 12
        value = m.group(0)
        conf = 0.5 if ambiguous else 0.75
        if not year:
            conf -= 0.15
        warn = None
        if ambiguous:
            warn = (f'The date "{value}" is ambiguous (day/month order) — '
                    "please confirm it.")
        elif not year:
            warn = f'The year was not visible for "{value}" — please confirm it.'
        push(value, round(conf * max(ocr_conf, 0.5), 2), None, warn)

    fields.sort(key=lambda fld: -fld.confidence)
    return fields, warnings


def find_times(text: str, ocr_conf: float) -> list[Field]:
    out: list[Field] = []
    seen: set[str] = set()
    for m in RE_TIME.finditer(text):
        if m.group(4):  # "7 pm" style
            hh, ampm = int(m.group(4)), (m.group(5) or "").lower()
            if hh > 12:
                continue
            value = f"{hh}:00 {ampm.upper()}"
        else:
            hh, mm, ampm = int(m.group(1)), m.group(2), (m.group(3) or "").lower()
            if hh > 24 or int(mm) > 59:
                continue
            value = f"{hh}:{mm}" + (f" {ampm.upper()}" if ampm else "")
        if value in seen:
            continue
        seen.add(value)
        conf = 0.8 if ampm else 0.62
        out.append(Field("time", "Time", value, round(conf * max(ocr_conf, 0.5), 2)))
        if len(out) >= 2:
            break
    return out


def find_contacts(text: str) -> list[Field]:
    out: list[Field] = []
    emails = RE_EMAIL.findall(text)
    if emails:
        out.append(Field("email", "Email", emails[0], 0.85))
    phones = [p for p in RE_PHONE.findall(text) if len(re.sub(r"\D", "", p)) >= 10]
    if phones:
        out.append(Field("phone", "Phone", _clean(phones[0]), 0.7))
    return out


def find_url(text: str) -> Field | None:
    m = RE_URL.search(text)
    if not m:
        return None
    url = m.group(0)
    if "@" in url:  # that's an email
        return None
    # Require a plausible TLD to reduce OCR noise ("abc.def" gibberish).
    if not re.search(r"\.(com|org|net|in|io|co|edu|gov|dev|ai|app|info)(/|\b)", url, re.IGNORECASE):
        return None
    return Field("url", "Link", url.lower(), 0.7)


# ----------------------------------------------------- per-category extractors


_MONEY_ONLY = re.compile(r"^[$€£₹\s\d.,]+$")


def _line_ok(line: str, min_len: int) -> bool:
    letters = sum(c.isalpha() for c in line)
    if len(line) < min_len or letters < 3 or len(line) > 80:
        return False
    if RE_DATE_NUMERIC.fullmatch(line) or _MONEY_ONLY.fullmatch(line):
        return False
    return True


def _guess_title(lines: list[str], min_len: int = 4, meta=None) -> tuple[str, float]:
    """Title = the most visually prominent line (largest glyphs) early in the
    image when OCR metadata is available; otherwise the first meaningful line.
    Never invents a title — only chooses among lines actually present."""
    if meta:
        scored = []
        for idx, (ln, h, top) in enumerate(meta):
            cleaned = _clean(ln)
            if _line_ok(cleaned, min_len) and h > 0:
                scored.append((idx, h, top, cleaned))
        if scored:
            max_h = max(h for _, h, _, _ in scored)
            big = [e for e in scored if e[1] >= max_h * 0.82]
            big.sort(key=lambda x: x[2])  # topmost among the large lines
            idx, h, top, text = big[0]
            # Headline split across two visually-adjacent lines? Join them.
            if idx + 1 < len(meta):
                ln2, h2, top2 = meta[idx + 1]
                cleaned2 = _clean(ln2)
                if (
                    h2 >= h * 0.72
                    and 0 < (top2 - top) < h * 1.65
                    and _line_ok(cleaned2, min_len)
                    and len(text) + len(cleaned2) <= 78
                ):
                    text = f"{text} {cleaned2}"
            conf = 0.8 if h >= 26 else 0.65
            return text, conf
    for ln in lines[:8]:
        cleaned = _clean(ln)
        if _line_ok(cleaned, min_len):
            conf = 0.75 if 8 <= len(cleaned) <= 50 else 0.55
            return cleaned, conf
    return (lines[0][:60] if lines else "Untitled"), 0.4


def extract_event(text, lines, ocr_conf, meta=None) -> Extraction:
    title, tconf = _guess_title(lines, meta=meta)
    fields: list[Field] = []
    dates, dwarn = find_dates(text, ocr_conf)
    times = find_times(text, ocr_conf)
    fields += dates[:1] + times[:1]

    venue = None
    for i, ln in enumerate(lines):
        m = re.search(r"\b(?:venue|at|location|where)\s*[:\-]?\s+(.{3,70})$", ln, re.IGNORECASE)
        if m and not RE_DATE_NUMERIC.search(m.group(1)):
            venue = _clean(m.group(1))
            break
    if venue is None:
        # Heuristic: a line with a place-ish suffix near a date line.
        for ln in lines:
            if re.search(r"\b(hall|centre|center|stadium|park|auditorium|theat(er|re)|grounds?|hotel|campus|arena|club)\b", ln, re.IGNORECASE) and 5 < len(ln) < 70:
                venue = _clean(ln)
                break
    if venue:
        fields.append(Field("location", "Venue", venue, 0.6))

    url = find_url(text)
    if url:
        fields.append(url)
    fields += find_contacts(text)[:1]

    warnings = dwarn
    if not dates:
        warnings.append("No event date was detected.")
    if not times:
        warnings.append("No start time was detected.")
    return Extraction(title, tconf, fields, warnings)


def extract_receipt(text, lines, ocr_conf, meta=None) -> Extraction:
    title, tconf = _guess_title(lines, min_len=3, meta=meta)
    fields: list[Field] = [Field("merchant", "Merchant", title, round(tconf * 0.9, 2))]

    dates, dwarn = find_dates(text, ocr_conf)
    fields += dates[:1]

    total_value = None
    total_conf = 0.0
    currency = None
    for ln in lines:
        m = re.search(r"\b(grand\s*)?total\b[:\s]*(.+)$", ln, re.IGNORECASE)
        if m:
            mm = RE_MONEY.search(m.group(2))
            if mm:
                total_value = _num(mm.group("amt"))
                total_conf = 0.85
                if mm.group("cur"):
                    currency = _norm_cur(mm.group("cur"))
        if currency is None:
            mm = RE_MONEY.search(ln)
            if mm and mm.group("cur"):
                currency = _norm_cur(mm.group("cur"))
    if total_value is None:
        amounts = [(float(_num(m.group("amt"))), m.group("cur"))
                   for m in RE_MONEY.finditer(text)
                   if _num(m.group("amt")).replace(".", "").isdigit() or "." in m.group("amt")]
        amounts = [(a, c) for a, c in amounts if a > 0]
        if amounts:
            best = max(amounts, key=lambda x: x[0])
            total_value = f"{best[0]:.2f}".rstrip("0").rstrip(".")
            total_conf = 0.45
            currency = currency or (CUR_SYMBOLS.get(best[1], _norm_cur(best[1])) if best[1] else None)
            dwarn.append('No explicit "Total" line — the largest amount is shown. Please confirm.')

    if total_value:
        fields.append(Field("total", "Total", str(total_value), round(total_conf * max(ocr_conf, 0.5), 2)))
    if currency:
        fields.append(Field("currency", "Currency", str(currency), 0.65))

    items = []
    for ln in lines:
        if RE_TOTAL_WORD.search(ln):
            continue
        m = re.match(r"^(.{3,40}?)\s+(?:[$€£₹]|Rs\.?)?\s?(\d[\d,]*\.\d{2})$", ln.strip())
        if m and len(items) < 10:
            name = _clean(m.group(1))
            if not name.lower().startswith(("tax", "vat", "gst", "cash", "card", "change", "subtotal")):
                items.append(f"{name} — {_num(m.group(2))}")
    if items:
        fields.append(Field("items", "Items", "\n".join(items), 0.6))

    if re.search(r"\b(warranty|guarantee)\b", text, re.IGNORECASE):
        fields.append(Field("warranty", "Warranty note", "Warranty mentioned on receipt", 0.55))
    if re.search(r"\b(return|exchange)\s+(by|before|within|policy)\b", text, re.IGNORECASE):
        fields.append(Field("returns", "Return note", "Return/exchange terms mentioned", 0.55))

    ref = RE_BOOKING_REF.search(text)
    if ref:
        fields.append(Field("reference", "Reference", ref.group(1), 0.65))
    return Extraction(title, tconf, fields, dwarn)


def extract_ticket(text, lines, ocr_conf, meta=None) -> Extraction:
    title, tconf = _guess_title(lines, meta=meta)
    fields: list[Field] = []
    dates, dwarn = find_dates(text, ocr_conf)
    times = find_times(text, ocr_conf)
    fields += dates[:1] + times[:1]

    seat = RE_SEAT.search(text)
    if seat:
        fields.append(Field("seat", "Seat", seat.group(1) or seat.group(2), 0.7))
    pnr = RE_PNR.search(text)
    if pnr:
        fields.append(Field("reference", "PNR / reference", pnr.group(1).upper(), 0.85))
    else:
        ref = RE_BOOKING_REF.search(text)
        if ref:
            fields.append(Field("reference", "Booking reference", ref.group(1).upper(), 0.7))

    route = re.search(r"\b([A-Z][a-zA-Z .]{2,20})\s*(?:→|->|to|-)\s*([A-Z][a-zA-Z .]{2,20})\b", text)
    if route and len(fields) < 8:
        fields.append(Field("route", "Route", f"{_clean(route.group(1))} → {_clean(route.group(2))}", 0.5))
    return Extraction(title, tconf, fields, dwarn)


def extract_notes(text, lines, ocr_conf, meta=None) -> Extraction:
    title, tconf = _guess_title(lines, min_len=3, meta=meta)
    fields: list[Field] = [Field("topic", "Topic", title, round(tconf * 0.85, 2))]
    n_words = len(text.split())
    fields.append(Field("length", "Length", f"~{n_words} words", 0.9))
    concepts: list[str] = []
    seen_concepts: set[str] = set()
    for ln in lines:
        m = re.match(r"^([A-Za-z][A-Za-z '’-]{2,28})\s*[:\-–]\s+(.{8,120})$", ln.strip())
        if m and len(concepts) < 8:
            term = _clean(m.group(1))
            key = term.lower()
            if key not in seen_concepts and key not in ("key points", "notes", "the equation"):
                seen_concepts.add(key)
                concepts.append(term)
    if concepts:
        fields.append(Field("concepts", "Key concepts", ", ".join(concepts), 0.6))
    return Extraction(title, tconf, fields, [])


def extract_menu(text, lines, ocr_conf, meta=None) -> Extraction:
    title, tconf = _guess_title(lines, min_len=3, meta=meta)
    fields: list[Field] = []
    dishes: list[str] = []
    for ln in lines:
        m = re.match(r"^(.{3,45}?)\s*\.{2,}\s*(?:[$€£₹]|Rs\.?)?\s?(\d[\d.,]*)$", ln.strip()) or \
            re.match(r"^(.{3,45}?)\s{1,4}(?:[$€£₹]|Rs\.?)\s?(\d[\d.,]*)$", ln.strip())
        if m and not RE_TOTAL_WORD.search(ln):
            dishes.append(f"{_clean(m.group(1))} — {_num(m.group(2))}")
    if dishes:
        fields.append(Field("dishes", "Dishes", "\n".join(dishes[:14]), round(0.75 * max(ocr_conf, 0.5), 2)))
        fields.append(Field("dish_count", "Dishes found", str(len(dishes)), 0.8))
    else:
        return Extraction(title, tconf, fields,
                          ["No dish/price lines were clearly readable — a flatter, sharper photo helps."])
    return Extraction(title, tconf, fields, [])


def extract_product(text, lines, ocr_conf, meta=None) -> Extraction:
    title, tconf = _guess_title(lines, min_len=3, meta=meta)
    fields: list[Field] = [Field("product", "Product", title, round(tconf * 0.9, 2))]
    model = RE_MODEL.search(text)
    if model:
        fields.append(Field("model", "Model", _clean(model.group(1)), 0.75))
    brand = None
    for ln in lines[:4]:
        if re.search(r"\b(by|from|brand)\b", ln, re.IGNORECASE):
            b = re.sub(r"\b(by|from|brand)\b[:\s]*", "", ln, flags=re.IGNORECASE)
            if 2 < len(_clean(b)) < 40:
                brand = _clean(b)
                break
    if brand:
        fields.append(Field("brand", "Brand", brand, 0.55))

    war = re.search(r"\b(\d+\s*(?:year|yr|month)s?)\s*(?:limited\s*)?warranty\b", text, re.IGNORECASE)
    if war:
        fields.append(Field("warranty", "Warranty", _clean(war.group(0)), 0.8))
    elif re.search(r"\bwarranty\b", text, re.IGNORECASE):
        fields.append(Field("warranty", "Warranty", "Warranty mentioned (term not readable)", 0.5))

    bb = re.search(r"\b(?:best before|exp(?:iry|ires)?|use by)[:\s]*([A-Za-z0-9 ./-]{4,20})", text, re.IGNORECASE)
    if bb:
        fields.append(Field("expiry", "Best before / expiry", _clean(bb.group(1)), 0.6))

    specs = []
    for ln in lines:
        if re.search(r"\d+\s*(mah|gb|tb|w|v|hz|mp|inch|\"|mm|cm|kg|g|ml|l)\b", ln, re.IGNORECASE) and len(ln) < 70:
            specs.append(_clean(ln))
        if len(specs) >= 5:
            break
    if specs:
        fields.append(Field("specs", "Specs on label", "\n".join(specs), 0.55))
    return Extraction(title, tconf, fields, [])


def extract_document(text, lines, ocr_conf, meta=None) -> Extraction:
    title, tconf = _guess_title(lines, meta=meta)
    if re.match(r"^(notice|circular|announcement|memo)\b", title or "", re.IGNORECASE):
        for ln in lines[1:4]:
            if re.search(r"\b(subject|re)\s*:", ln, re.IGNORECASE):
                cand = _clean(re.sub(r"^(subject|re)\s*:\s*", "", ln, flags=re.IGNORECASE))
                if len(cand) > 4:
                    title, tconf = cand[:80], 0.75
                    break
    fields: list[Field] = []
    dates, dwarn = find_dates(text, ocr_conf)
    fields += dates[:2]

    for i, ln in enumerate(lines):
        if re.search(r"\b(deadline|due date|last date|submit by|respond by)\b", ln, re.IGNORECASE):
            scope = ln + " " + (lines[i + 1] if i + 1 < len(lines) else "")
            dfields, _ = find_dates(scope, ocr_conf)
            if dfields:
                fields.append(Field("deadline", "Deadline", dfields[0].value, 0.6))
            break

    fields += find_contacts(text)
    url = find_url(text)
    if url:
        fields.append(url)
    return Extraction(title, tconf, fields, dwarn)


def extract_other(text, lines, ocr_conf, meta=None) -> Extraction:
    title, tconf = _guess_title(lines, meta=meta)
    fields: list[Field] = []
    if text.strip():
        fields.append(Field("length", "Text found", f"{len(text.split())} words", 0.85))
    dates, _ = find_dates(text, ocr_conf)
    fields += dates[:1]
    fields += find_contacts(text)[:1]
    url = find_url(text)
    if url:
        fields.append(url)
    return Extraction(title, tconf, fields, [])


EXTRACTORS = {
    "event": extract_event,
    "receipt": extract_receipt,
    "ticket": extract_ticket,
    "notes": extract_notes,
    "menu": extract_menu,
    "product": extract_product,
    "document": extract_document,
    "other": extract_other,
}


def extract(category: str, text: str, ocr_conf: float, meta=None) -> Extraction:
    lines = [ln for ln in text.splitlines() if ln.strip()]
    fn = EXTRACTORS.get(category, extract_other)
    result = fn(text, lines, ocr_conf, meta=meta)
    # Enforce honesty: drop empty values, clamp confidences.
    result.fields = [
        f for f in result.fields
        if f.value and f.value.strip()
    ]
    for f in result.fields:
        f.confidence = max(0.05, min(0.98, round(f.confidence, 2)))
    return result
