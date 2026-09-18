"""Analysis pipeline orchestrator.

media bytes -> [sanitized] -> OCR -> classify -> extract -> actions -> result

Prompt-injection posture: this pipeline never hands OCR text to an
instruction-following model, so text inside a poster/note/screenshot can never
become instructions. Should an LLM provider be added later, OCR text MUST be
wrapped as data (never interpolated into system instructions) — see README.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field as dc_field

from . import classify as classify_mod
from . import extract as extract_mod
from .actions_engine import ActionSpec, suggest_actions
from .ocr import OcrError, extract_text

# Strip control characters & bidi overrides (used in unicode spoofing).
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f\u202a-\u202e\u2066-\u2069]")


def sanitize_untrusted(text: str, max_chars: int) -> str:
    text = _CONTROL.sub("", text)
    return text[:max_chars]


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


def run_pipeline(image_bytes: bytes, max_chars: int = 20_000) -> PipelineResult:
    warnings: list[str] = []
    partial = False

    try:
        ocr = extract_text(image_bytes, max_chars=max_chars)
    except OcrError as exc:
        # No text at all — still return a graceful result with fallback actions.
        return PipelineResult(
            category="other",
            category_confidence=0.1,
            category_reasons=["The image could not be read."],
            title="Image",
            title_confidence=0.3,
            fields=[],
            actions=suggest_actions("other", {}),
            text="",
            warnings=[str(exc)],
            partial=True,
        )

    text = sanitize_untrusted(ocr.text, max_chars)

    if ocr.word_count < 6:
        warnings.append(
            "We could only read a little text from this image — a clearer, "
            "closer photo gives better results."
        )
    if ocr.mean_confidence and ocr.mean_confidence < 0.55:
        warnings.append("Some words were hard to read — please double-check the details.")
        partial = True

    # Prompt-injection surface note: text like "ignore all previous
    # instructions" is inert here (no instruction-following model consumes it),
    # but we still flag it transparently to build user trust.
    injection_like = bool(
        re.search(r"(ignore|disregard)[ -~]{0,60}(instruction|prompt)|previous instructions",
                  text, re.IGNORECASE)
    )
    if injection_like:
        warnings.append(
            "This image contains text that looks like instructions for an AI. "
            "LifeClip treats text in photos as data, never as commands."
        )

    classification = classify_mod.classify(text, ocr.word_count)
    if injection_like:
        # Adversarial wording can skew keyword classification — stay humble.
        classification = classify_mod.Classification(
            classification.category,
            min(classification.confidence, 0.45),
            classification.reasons + ["wording may be misleading — please check the category"],
        )
    meta = [(ln.text, ln.mean_height, ln.top) for ln in ocr.lines]
    extraction = extract_mod.extract(
        classification.category, text, ocr.mean_confidence or 0.6, meta=meta
    )

    fields_by_name = {f.name: f.value for f in extraction.fields}
    actions = suggest_actions(classification.category, fields_by_name)

    warnings = extraction.warnings + warnings
    if classification.category == "other":
        warnings.append("We couldn't tell what kind of item this is, so we kept things simple.")

    return PipelineResult(
        category=classification.category,
        category_confidence=classification.confidence,
        category_reasons=classification.reasons,
        title=extraction.title,
        title_confidence=extraction.title_confidence,
        fields=extraction.fields,
        actions=actions,
        text=text,
        warnings=warnings[:6],
        partial=partial,
    )
