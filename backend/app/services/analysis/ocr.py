"""OCR via Tesseract (runs locally, no external API, nothing leaves the server).

We do light, careful preprocessing:
  - EXIF orientation correction (phone photos)
  - cap longest side (OCR is slower, not better, past ~2500px)
  - grayscale + autocontrast (helps phone captures of paper)

We also collect Tesseract's per-word confidence so downstream fields can carry
honest confidence values rather than invented certainty.
"""

from __future__ import annotations

import io
from dataclasses import dataclass, field

import pytesseract
from PIL import Image, ImageOps


class OcrError(Exception):
    pass


@dataclass
class OcrLine:
    text: str
    mean_height: float   # average glyph height -> approximates visual prominence
    top: int             # y position in the preprocessed image


@dataclass
class OcrResult:
    text: str
    mean_confidence: float           # 0..1 across recognized words
    word_count: int
    lines: list[OcrLine] = field(default_factory=list)
    low_confidence_words: list[str] = field(default_factory=list)


def _prep(image_bytes: bytes) -> Image.Image:
    try:
        img = Image.open(io.BytesIO(image_bytes))
        img.load()
    except Exception as exc:
        raise OcrError("That file doesn't look like a readable image.") from exc

    img = ImageOps.exif_transpose(img)
    if img.mode not in ("L", "RGB"):
        img = img.convert("RGB")

    max_side = 2500
    w, h = img.size
    if max(w, h) > max_side:
        scale = max_side / max(w, h)
        img = img.resize((max(1, int(w * scale)), max(1, int(h * scale))), Image.LANCZOS)
    # Upscale very small images — Tesseract needs ~30px+ x-height.
    if max(img.size) < 1000:
        scale = 1000 / max(img.size)
        img = img.resize((int(img.width * scale), int(img.height * scale)), Image.LANCZOS)

    gray = ImageOps.grayscale(img)
    return ImageOps.autocontrast(gray, cutoff=1)


def extract_text(image_bytes: bytes, max_chars: int = 20_000) -> OcrResult:
    img = _prep(image_bytes)
    try:
        data = pytesseract.image_to_data(
            img, config="--oem 3 --psm 3", output_type=pytesseract.Output.DICT
        )
    except pytesseract.TesseractNotFoundError as exc:
        raise OcrError(
            "The OCR engine (Tesseract) is not installed on the server."
        ) from exc
    except Exception as exc:
        raise OcrError("We couldn't read this image. A clearer photo may help.") from exc

    words: list[str] = []
    confs: list[float] = []
    low: list[str] = []
    lines: dict[tuple[int, int, int], list[tuple[int, str, int, int]]] = {}

    n = len(data.get("text", []))
    for i in range(n):
        text = (data["text"][i] or "").strip()
        try:
            conf = float(data["conf"][i])
        except (TypeError, ValueError):
            conf = -1.0
        if not text or conf < 0:
            continue
        key = (
            int(data["block_num"][i]),
            int(data["par_num"][i]),
            int(data["line_num"][i]),
        )
        lines.setdefault(key, []).append(
            (int(data["left"][i]), text, int(data["height"][i]), int(data["top"][i]))
        )
        if len(text) > 1 or text.isalnum():
            confs.append(conf)
            if conf < 45 and len(low) < 12:
                low.append(text)

    # Rebuild reading order: block/paragraph/line, words sorted left-to-right.
    ordered_keys = sorted(lines.keys())
    out_lines = []
    out_meta: list[OcrLine] = []
    for key in ordered_keys:
        entries = sorted(lines[key], key=lambda x: x[0])
        words_sorted = [t for _, t, _, _ in entries]
        line_text = " ".join(words_sorted)
        out_lines.append(line_text)
        words.extend(words_sorted)
        alpha_heights = [h for _, t, h, _ in entries if sum(c.isalpha() for c in t) >= 1 and h > 0]
        mean_h = sum(alpha_heights) / len(alpha_heights) if alpha_heights else 0.0
        out_meta.append(OcrLine(line_text, round(mean_h, 1), entries[0][3] if entries else 0))

    text = "\n".join(out_lines).strip()
    if len(text) > max_chars:
        text = text[:max_chars]

    mean = (sum(confs) / len(confs) / 100.0) if confs else 0.0
    return OcrResult(
        text=text,
        mean_confidence=round(mean, 3),
        word_count=len(words),
        lines=out_meta,
        low_confidence_words=low,
    )
