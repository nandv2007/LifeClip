"""Explainable, content-only category classification.

Scores combine vocabulary and layout/structure from extracted media text.
Filenames, upload paths and test identities are intentionally unavailable here.
The notes detector recognizes educational semantics plus handwritten/short-line,
formula, definition, heading, bullet and diagram structures without weakening
strong receipt, ticket, event, menu, product or formal-document evidence.
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
_BULLET = re.compile(r"^\s*(?:[-•*▪◦]|\d{1,2}[.)]|[a-z][.)])\s+")
_DEFINITION = re.compile(r"\b(?:is|are)\s+(?:defined as|called|the process|a |an )|\bmeans\b|^[^:]{2,35}:\s+\S", re.IGNORECASE)
_EQUATION = re.compile(r"(?:[A-Za-z0-9)]\s*[=≈→⇌]\s*[A-Za-z0-9(]|\b\w+\s*\^?\d*\s*[+÷×]\s*\w+)")
_DIAGRAM = re.compile(r"\b(diagram|figure|labelled|label the|flowchart|cross[- ]section|axis|axes)\b|[-=]+>")
_ACADEMIC = re.compile(
    r"\b(?:photosynthesis|respiration|chlorophyll|cell|nucleus|enzyme|genetics|mitosis|"
    r"atom|molecule|compound|reaction|covalent|oxidation|acid|base|"
    r"force|velocity|acceleration|momentum|energy|circuit|voltage|current|"
    r"equation|theorem|derivative|integral|matrix|probability|geometry|algebra|calculus|"
    r"algorithm|database|data structure|complexity|programming|binary|network|"
    r"empire|revolution|civilization|colonial|treaty|"
    r"demand|supply|inflation|economics|elasticity|"
    r"climate|latitude|longitude|erosion|tectonic|grammar|metaphor)\b",
    re.IGNORECASE,
)

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
        ("chapter", 1.5), ("definition", 1.75), ("theorem", 2), ("formula", 1.75),
        ("notes", 2), ("summary", 1), ("example", 0.5), ("question", 0.5),
        ("study", 1.5), ("revision", 2.25), ("exam", 1.5), ("lecture", 2.25),
        ("unit", 0.5), ("topic", 1), ("remember", 1), ("key points", 2),
        ("learning objective", 2.5), ("homework", 1.5), ("class notes", 3),
        ("important points", 2), ("advantages", 1), ("disadvantages", 1),
        ("properties", 0.75), ("types of", 0.75), ("steps", 0.75),
        ("concept", 1), ("hypothesis", 1.5), ("proof", 1.25),
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


def _structure_signals(lines: list[str], text: str) -> dict[str, tuple[float, list[str]]]:
    signals: dict[str, tuple[float, list[str]]] = {}
    if not lines:
        return signals

    def add(category: str, amount: float, reason: str) -> None:
        score, reasons = signals.get(category, (0.0, []))
        signals[category] = (score + amount, reasons + ([reason] if reason not in reasons else []))

    money_lines = sum(1 for line in lines if _MONEY.search(line))
    price_like = sum(1 for line in lines if _PRICE_LINE.match(line.strip()) and len(line) < 60)
    total_hit = any(_TOTAL_WORD.search(line) for line in lines)
    if price_like >= 4 and money_lines / max(len(lines), 1) > 0.3:
        add("menu", 4, "multiple dish/price-style lines")
    if total_hit:
        add("receipt", 4, "an explicit total line")
        add("menu", -1, "")
    if money_lines >= 6 and not total_hit and price_like >= 4:
        add("menu", 1, "price-list layout")
    if _DATE.search(text) and _TIME.search(text):
        add("event", 1.0, "date and time layout")
        add("ticket", 0.5, "date and time layout")

    # Formal prose is useful evidence for both notes and documents, but unlike
    # the old detector it is no longer the only structure notes can use.
    long_lines = sum(1 for line in lines if len(line) > 60)
    if long_lines / max(len(lines), 1) > 0.5 and money_lines == 0:
        add("notes", 1.0, "explanatory text layout")
        add("document", 1.0, "formal text layout")

    if money_lines == 0:
        bullet_count = sum(1 for line in lines if _BULLET.match(line))
        definition_count = sum(1 for line in lines if _DEFINITION.search(line))
        equation_count = sum(1 for line in lines if _EQUATION.search(line))
        heading_count = sum(
            1 for line in lines
            if 2 <= len(line.split()) <= 10 and (line.endswith(":") or line.isupper())
        )
        short_lines = sum(1 for line in lines if 3 <= len(line.split()) <= 12)
        academic_count = len(_ACADEMIC.findall(text))

        if bullet_count >= 2:
            add("notes", min(2.0, 0.5 + bullet_count * 0.25), "bullet/numbered points")
        if definition_count:
            add("notes", min(2.25, 1.1 + definition_count * 0.35), "definition-style statements")
        if equation_count:
            add("notes", min(2.5, 1.2 + equation_count * 0.45), "formula/equation notation")
        if heading_count >= 2:
            add("notes", 1.0, "section headings")
        if _DIAGRAM.search(text):
            add("notes", 1.75, "diagram/flow notation")
        if academic_count >= 2:
            add("notes", min(3.0, 1.25 + academic_count * 0.35), "subject terminology")
        elif academic_count == 1 and (bullet_count or definition_count or equation_count or short_lines >= 4):
            add("notes", 1.25, "subject terminology with note-like layout")
        # Short handwriting commonly OCRs into many brief lines; require an
        # educational signal to avoid labeling arbitrary signs as notes.
        if short_lines >= 5 and (academic_count or definition_count or equation_count):
            add("notes", 1.0, "short handwritten-style lines")

    return signals


def classify(text: str, word_count: int) -> Classification:
    if word_count == 0 or len(text.strip()) < 3:
        return Classification("other", 0.2, ["There was very little readable text in this file."])

    lower = text.lower()
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    scores: dict[str, float] = {category: 0.0 for category in CATEGORIES if category != "other"}
    reasons: dict[str, list[str]] = {category: [] for category in scores}

    for category, phrases in KEYWORDS.items():
        for phrase, weight in phrases:
            # Word boundaries stop short tokens such as "unit" matching inside
            # unrelated words while still accepting punctuation around a phrase.
            if re.search(rf"(?<!\w){re.escape(phrase)}(?!\w)", lower):
                scores[category] += weight
                if len(reasons[category]) < 3:
                    reasons[category].append(f'found "{phrase}"')

    for category, (boost, structural_reasons) in _structure_signals(lines, text).items():
        scores[category] = scores.get(category, 0.0) + boost
        if boost > 0:
            for reason in structural_reasons:
                if reason and len(reasons.setdefault(category, [])) < 5:
                    reasons[category].append(reason)

    best = max(scores, key=lambda category: scores[category])
    ranked = sorted(scores.values(), reverse=True)
    runner_up = ranked[1] if len(ranked) > 1 else 0.0

    # Keep Other for genuinely unsupported/ambiguous material. Notes earn the
    # threshold from independent content/structure evidence, not a global cut.
    if scores[best] < 2.5:
        return Classification("other", 0.35, ["This doesn't clearly match a known content type."])

    spread = scores[best] - runner_up
    confidence = min(0.95, 0.45 + scores[best] * 0.06 + max(spread, 0) * 0.04)
    why = (reasons.get(best) or ["overall wording and layout"])[:5]
    if spread < 1.0:
        why.append("another category was close — please check")
    return Classification(best, round(confidence, 2), why)
