"""Grounded image analysis pipeline.

Explicitly selected JPEG/PNG/WebP bytes pass through local Tesseract OCR,
content classification, deterministic field extraction and grounded actions.
Filenames and upload paths are never available to classification.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field as dc_field
from typing import Callable

from . import classify as classify_mod
from . import extract as extract_mod
from .actions_engine import ActionSpec, suggest_actions
from .ocr import OcrError, OcrResult, extract_text

_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f\u202a-\u202e\u2066-\u2069]")
PhaseCallback = Callable[[str], None]


def sanitize_untrusted(text: str, max_chars: int) -> str:
    return _CONTROL.sub("", text)[:max_chars]


@dataclass
class PipelineResult:
    category: str
    category_confidence: float
    category_reasons: list[str]
    title: str
    title_confidence: float
    fields: list[extract_mod.Field]
    actions: list[ActionSpec]
    text: str
    warnings: list[str] = dc_field(default_factory=list)
    partial: bool = False
    text_status: str = "unreadable"
    ocr_used: bool = True
    subject: str = ""
    topic: str = ""
    headings: list[str] = dc_field(default_factory=list)
    concepts: list[str] = dc_field(default_factory=list)


def _phase(callback: PhaseCallback | None, value: str) -> None:
    if callback:
        callback(value)


def _subject(text: str) -> str:
    """Return a broad subject only when its vocabulary occurs in the source."""
    groups = {
        "Biology": ("cell", "photosynthesis", "respiration", "enzyme", "genetics", "ecology", "organism", "chlorophyll", "mitosis"),
        "Chemistry": ("atom", "molecule", "reaction", "acid", "base", "compound", "molar", "oxidation", "covalent"),
        "Physics": ("force", "velocity", "acceleration", "momentum", "energy", "circuit", "voltage", "current", "optics"),
        "Mathematics": ("theorem", "equation", "derivative", "integral", "matrix", "probability", "geometry", "algebra", "calculus"),
        "Computer Science": ("algorithm", "database", "programming", "complexity", "data structure", "network", "operating system", "binary"),
        "History": ("empire", "revolution", "dynasty", "civilization", "century", "colonial", "treaty"),
        "Economics": ("demand", "supply", "inflation", "market", "gdp", "elasticity", "macroeconomic", "microeconomic"),
        "Geography": ("climate", "latitude", "longitude", "erosion", "river basin", "population", "tectonic"),
        "Language": ("grammar", "noun", "verb", "adjective", "literature", "metaphor", "poem"),
    }
    low = text.lower()
    scored = [(sum(1 for term in terms if re.search(rf"\b{re.escape(term)}\b", low)), name) for name, terms in groups.items()]
    score, name = max(scored, default=(0, ""))
    return name if score >= 1 else ""


def _headings(text: str) -> list[str]:
    out: list[str] = []
    for line in text.splitlines():
        clean = line.strip(" \t•*-–—")
        words = clean.split()
        if not (2 <= len(words) <= 10 and 4 <= len(clean) <= 80):
            continue
        is_heading = clean.isupper() or clean.endswith(":") or (
            clean == clean.title() and not re.search(r"[.!?]$", clean)
        )
        if is_heading and clean not in out:
            out.append(clean.rstrip(":"))
        if len(out) >= 12:
            break
    return out


def _concepts(fields: list[extract_mod.Field], text: str) -> list[str]:
    from_field = next((field.value for field in fields if field.name == "concepts"), "")
    if from_field:
        return [item.strip() for item in from_field.split(",") if item.strip()][:12]
    out: list[str] = []
    for line in text.splitlines():
        match = re.match(r"^\s*([A-Za-z][A-Za-z /'’()-]{2,40})\s*[:–—-]\s+.{8,}", line)
        if match:
            term = match.group(1).strip()
            if term.lower() not in {item.lower() for item in out}:
                out.append(term)
        if len(out) >= 12:
            break
    return out


def _fallback(message: str) -> PipelineResult:
    return PipelineResult(
        category="other",
        category_confidence=0.1,
        category_reasons=["The image could not be read."],
        title="Image",
        title_confidence=0.3,
        fields=[],
        actions=suggest_actions("other", {}),
        text="",
        warnings=[message],
        partial=True,
        text_status="unreadable",
        ocr_used=True,
    )


def _analyze_text(
    source: OcrResult,
    *,
    max_chars: int,
    phase_callback: PhaseCallback | None = None,
) -> PipelineResult:
    warnings: list[str] = []
    partial = False
    text = sanitize_untrusted(source.text, max_chars)

    if source.word_count < 6:
        warnings.append(
            "We could only read a little text from this image — a clearer, closer photo may help."
        )
    if source.mean_confidence and source.mean_confidence < 0.55:
        warnings.append("Some words were hard to read — please double-check the details.")
        partial = True

    injection_like = bool(re.search(
        r"(ignore|disregard)[ -~]{0,60}(instruction|prompt)|previous instructions",
        text,
        re.IGNORECASE,
    ))
    if injection_like:
        warnings.append(
            "This image contains text that looks like instructions for an AI. "
            "LifeClip treats image text as data, never as commands."
        )

    _phase(phase_callback, "classifying")
    classification = classify_mod.classify(text, source.word_count)
    if injection_like:
        classification = classify_mod.Classification(
            classification.category,
            min(classification.confidence, 0.45),
            classification.reasons + ["wording may be misleading — please check the category"],
        )

    _phase(phase_callback, "organizing")
    meta = [(line.text, line.mean_height, line.top) for line in source.lines]
    extraction = extract_mod.extract(
        classification.category, text, source.mean_confidence or 0.6, meta=meta
    )
    fields_by_name = {field.name: field.value for field in extraction.fields}
    actions = suggest_actions(classification.category, fields_by_name)
    warnings = extraction.warnings + warnings
    if classification.category == "other":
        warnings.append("We couldn't confidently identify this item, so it is ready for review in Other.")

    subject = _subject(text) if classification.category == "notes" else ""
    topic = fields_by_name.get("topic", "") if classification.category == "notes" else ""
    if not text.strip():
        text_status = "unreadable"
    elif partial or source.mean_confidence < 0.55:
        text_status = "low_confidence"
    else:
        text_status = "ocr"

    return PipelineResult(
        category=classification.category,
        category_confidence=classification.confidence,
        category_reasons=classification.reasons,
        title=extraction.title,
        title_confidence=extraction.title_confidence,
        fields=extraction.fields,
        actions=actions,
        text=text,
        warnings=warnings[:10],
        partial=partial,
        text_status=text_status,
        ocr_used=True,
        subject=subject,
        topic=topic,
        headings=_headings(text),
        concepts=_concepts(extraction.fields, text),
    )


def run_pipeline(
    image_bytes: bytes,
    max_chars: int = 20_000,
    phase_callback: PhaseCallback | None = None,
) -> PipelineResult:
    _phase(phase_callback, "extracting_text")
    try:
        ocr = extract_text(image_bytes, max_chars=max_chars)
    except OcrError as exc:
        return _fallback(str(exc))
    return _analyze_text(ocr, max_chars=max_chars, phase_callback=phase_callback)
