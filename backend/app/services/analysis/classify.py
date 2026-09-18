"""Category classification — deterministic weighted scoring over OCR output.

This is deliberately rule-based rather than a black-box model: it is fast,
runs fully offline, and its decisions are explainable (we can surface *why* a
category was chosen). Scores come from keyword evidence, structural evidence
(price-list density for menus, etc.) and a few negative signals.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

CATEGORIES = ("event", "receipt", "ticket", "notes", "menu", "product", "document", "other")

_MONEY = re.compile(r"(?:[$€£₹]|Rs\.?|INR|USD|EUR)\s?\d|\d+\.\d{2}", re.IGNORECASE)
_PRICE_LINE = re.compile(r"^.+(?:[$€£₹]|Rs\.?)\s?\d[\d,.]*\s*$|^.+\s\d+\.\d{2}\s*$")
_TOTAL_WORD = re.compile(r"\b(total|amount due|grand total|balance|subtotal)\b", re.IGNORECASE)
_DATE = re.compile(
    r"\b(\d{1,2}[/-]\d{1,2}([/-]\d{2,4})?|\d{1,2}\s+(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)"
    r"|(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+\d{1,2})\b",
    re.IGNORECASE,
)
_TIME = re.compile(r"\b\d{1,2}[:.]\d{2}\s*(am|pm)?\b|\b\d{1,2}\s*(am|pm)\b", re.IGNORECASE)

KEYWORDS: dict[str, list[tuple[str, float]]] = {
    "event": [
        ("concert", 3), ("festival", 3), ("conference", 3), ("meetup", 2.5),
        ("workshop", 2.5), ("webinar", 2.5), ("live", 1.5), ("show", 1.5),
        ("venue", 2.5), ("doors open", 3), ("tickets", 1.5), ("rsvp", 2.5),
        ("featuring", 1.5), ("presents", 1.5), ("entry", 1), ("free entry", 2.5),
        ("summit", 2.5), ("expo", 2.5), ("party", 2), ("ceremony", 2),
    ],
    "receipt": [
        ("receipt", 3), ("invoice", 2.5), ("order", 1), ("cashier", 2.5),
        ("change", 1.5), ("tender", 2), ("vat", 1.5), ("gst", 1.5), ("tax", 1.5),
        ("qty", 2), ("bill", 1.5), ("thank you for", 2), ("store", 1),
        ("payment", 1.5), ("card", 0.5), ("visa", 1), ("upi", 1.5),
    ],
    "ticket": [
        ("ticket", 2.5), ("boarding pass", 4), ("pnr", 4), ("seat", 2.5),
        ("gate", 2), ("platform", 2.5), ("departure", 2.5), ("arrival", 1.5),
        ("passenger", 3), ("booking reference", 3.5), ("e-ticket", 4),
        ("flight", 2.5), ("train", 2.5), ("bus", 1.5), ("coach", 1),
        ("admit one", 4), ("row", 1.5), ("boarding", 2), ("journey", 1.5),
        ("reservation", 2), ("class", 0.5), ("pnr no", 4),
    ],
    "notes": [
        ("chapter", 1.5), ("definition", 1.5), ("theorem", 2), ("formula", 1.5),
        ("notes", 2), ("summary", 1), ("example", 0.5), ("question", 0.5),
        ("study", 1.5), ("revision", 2), ("exam", 1.5), ("lecture", 2),
        ("unit", 0.5), ("topic", 1), ("remember", 1), ("key points", 2),
    ],
    "menu": [
        ("menu", 3), ("starters", 3), ("appetizers", 3), ("mains", 2.5),
        ("desserts", 3), ("beverages", 3), ("drinks", 2), ("chef", 1.5),
        ("served with", 2), ("breakfast", 1.5), ("lunch", 1), ("dinner", 1),
        ("veg", 0.5), ("chicken", 0.75), ("paneer", 1), ("pizza", 1),
        ("combo", 1), ("thali", 1.5),
    ],
    "product": [
        ("ingredients", 2.5), ("nutrition", 2.5), ("net wt", 3), ("net weight", 3),
        ("mrp", 3), ("expiry", 2), ("best before", 2.5), ("manufactured", 2.5),
        ("model", 2), ("warranty", 2.5), ("serial", 2), ("barcode", 1.5),
        ("imported by", 2), ("marketed by", 2), ("fssai", 3), ("batch", 1.5),
        ("made in", 1.5), ("instructions", 1), ("capacity", 1), ("volts", 1.5),
        ("mah", 1.5), ("bluetooth", 1.5),
    ],
    "document": [
        ("notice", 3), ("hereby", 3), ("subject", 2), ("dear", 1.5),
        ("sincerely", 2.5), ("regards", 1.5), ("deadline", 2.5), ("circular", 3),
        ("announcement", 2.5), ("attention", 1.5), ("please be informed", 3),
        ("effective", 1.5), ("policy", 1.5), ("agreement", 2), ("memo", 2.5),
        ("office", 0.5), ("department", 1), ("ref no", 2), ("to whom", 1.5),
    ],
}


@dataclass
class Classification:
    category: str
    confidence: float
    reasons: list[str]


def _structure_signals(lines: list[str]) -> dict[str, float]:
    signals: dict[str, float] = {}
    if not lines:
        return signals

    money_lines = sum(1 for ln in lines if _MONEY.search(ln))
    price_like = sum(1 for ln in lines if _PRICE_LINE.match(ln.strip()) and len(ln) < 60)
    total_hit = any(_TOTAL_WORD.search(ln) for ln in lines)

    if price_like >= 4 and money_lines / max(len(lines), 1) > 0.3:
        signals["menu"] = signals.get("menu", 0) + 4
    if total_hit:
        signals["receipt"] = signals.get("receipt", 0) + 4
        signals["menu"] = signals.get("menu", 0) - 1
    if money_lines >= 6 and not total_hit and price_like >= 4:
        signals["menu"] = signals.get("menu", 0) + 1
    if _DATE.search(" ".join(lines)) and _TIME.search(" ".join(lines)):
        signals["event"] = signals.get("event", 0) + 1.0
        signals["ticket"] = signals.get("ticket", 0) + 0.5

    long_lines = sum(1 for ln in lines if len(ln) > 60)
    if long_lines / max(len(lines), 1) > 0.5 and money_lines == 0:
        signals["notes"] = signals.get("notes", 0) + 1.5
        signals["document"] = signals.get("document", 0) + 1.0
    return signals


def classify(text: str, word_count: int) -> Classification:
    if word_count == 0 or len(text.strip()) < 3:
        return Classification("other", 0.2, ["There was very little readable text in this image."])

    lower = text.lower()
    lines = [ln.strip() for ln in lower.splitlines() if ln.strip()]
    scores: dict[str, float] = {c: 0.0 for c in CATEGORIES if c != "other"}
    reasons: dict[str, list[str]] = {c: [] for c in scores}

    for category, words in KEYWORDS.items():
        for phrase, weight in words:
            if phrase in lower:
                scores[category] += weight
                if len(reasons[category]) < 3:
                    reasons[category].append(f'found "{phrase}"')

    for category, boost in _structure_signals(lines).items():
        scores[category] = scores.get(category, 0.0) + boost
        if boost > 0:
            reasons.setdefault(category, []).append("layout evidence")

    best = max(scores, key=lambda c: scores[c])
    runner_up = sorted(scores.values(), reverse=True)[1] if len(scores) > 1 else 0.0

    if scores[best] < 2.5:
        return Classification(
            "other", 0.35, ["This doesn't clearly match a known document type."]
        )

    spread = scores[best] - runner_up
    confidence = min(0.95, 0.45 + scores[best] * 0.06 + max(spread, 0) * 0.04)
    why = reasons.get(best) or ["overall wording"]
    if spread < 1.0:
        why.append("another category was close — please check")
    return Classification(best, round(confidence, 2), why)
