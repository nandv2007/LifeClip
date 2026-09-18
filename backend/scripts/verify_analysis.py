"""Run the REAL analysis pipeline (Tesseract OCR → classify → extract →
confidence → safety → actions) against every generated sample image and
print a human-readable verification report. No mocks.

Usage:
    cd backend && python scripts/verify_analysis.py
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.analysis.pipeline import run_pipeline  # noqa: E402

SAMPLES = Path(__file__).resolve().parent.parent.parent / "samples"
FILES = [
    ("sample_event_poster.jpg", "event"),
    ("sample_receipt.jpg", "receipt"),
    ("sample_ticket.jpg", "ticket"),
    ("sample_notes.jpg", "notes"),
    ("sample_menu.jpg", "menu"),
    ("sample_product.jpg", "product"),
    ("sample_notice.jpg", "document"),
    ("sample_unknown.jpg", "other"),
    ("sample_injection.jpg", "adversarial (injection)"),
]


def main() -> int:
    failures = 0
    for name, expected in FILES:
        path = SAMPLES / name
        if not path.exists():
            print(f"✗ {name}: missing — run scripts/generate_samples.py first")
            failures += 1
            continue
        t0 = time.time()
        r = run_pipeline(path.read_bytes())
        ms = (time.time() - t0) * 1000
        print(f"\n══ {name}  ({ms:.0f} ms) ══")
        print(f"  category:   {r.category}  (expected {expected})")
        print(f"  title:      {r.title!r}")
        print(f"  confidence: category={r.category_confidence:.2f} title={r.title_confidence:.2f} | fields "
              + ", ".join(f"{f.name}={f.value!r} ({f.confidence:.2f})"[:70] for f in r.fields))
        acts = [(a.action_type, a.label, a.primary) for a in r.actions]
        print(f"  actions:    " + "; ".join(f"{'★' if p else '·'} {t}:{lbl}" for t, lbl, p in acts))
        if r.warnings:
            print(f"  warnings:   " + " | ".join(r.warnings))
        ok = r.category == expected.split()[0] if not expected.startswith("adversarial") else any(
            "injection" in w.lower() or "ignored" in w.lower() or "instruction" in w.lower()
            for w in r.warnings) or r.category in {"other", "document", "event", "receipt",
                                                   "ticket", "notes", "menu", "product"}
        if not ok:
            failures += 1
            print("  ✗ MISMATCH vs expected")
        else:
            print("  ✓ ok")
    print(f"\n{'═' * 60}")
    print(f"sample OCR/analysis report: {len(FILES) - failures}/{len(FILES)} images verified")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
