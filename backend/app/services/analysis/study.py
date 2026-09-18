"""Local study tools for notes/documents — real, deterministic, offline.

These are classic NLP algorithms (frequency-based extractive summarization,
cloze-deletion quiz generation, term:definition flashcard parsing). They never
invent content: everything returned is grounded in the extracted text.
"""

from __future__ import annotations

import re

STOPWORDS = {
    "the", "a", "an", "and", "or", "but", "if", "then", "than", "that", "this",
    "these", "those", "is", "are", "was", "were", "be", "been", "being", "of",
    "to", "in", "on", "for", "with", "as", "by", "at", "from", "it", "its",
    "into", "about", "over", "after", "before", "between", "so", "such", "not",
    "no", "can", "could", "should", "would", "will", "shall", "may", "might",
    "we", "you", "they", "he", "she", "i", "their", "our", "your", "his", "her",
}


def _sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+|\n+", text)
    return [p.strip() for p in parts if len(p.strip()) >= 15]


def _word_freq(text: str) -> dict[str, float]:
    words = re.findall(r"[a-zA-Z][a-zA-Z'’-]{2,}", text.lower())
    freq: dict[str, float] = {}
    for w in words:
        if w not in STOPWORDS:
            freq[w] = freq.get(w, 0) + 1
    if freq:
        top = max(freq.values())
        freq = {w: c / top for w, c in freq.items()}
    return freq


def summarize(text: str, max_points: int = 6) -> list[dict]:
    sentences = _sentences(text)
    if not sentences:
        return []
    freq = _word_freq(text)
    scored = []
    for idx, s in enumerate(sentences):
        words = re.findall(r"[a-zA-Z][a-zA-Z'’-]{2,}", s.lower())
        score = sum(freq.get(w, 0) for w in words) / max(len(words), 1)
        scored.append((idx, score))
    keep = sorted(sorted(scored, key=lambda x: -x[1])[:max_points])
    return [{"point": sentences[idx][:300]} for idx, _ in keep]


def explain(text: str) -> list[dict]:
    """Plain-words view: the strongest sentences + key terms used in them."""
    points = summarize(text, 4)
    freq = _word_freq(text)
    terms = sorted(freq, key=lambda w: -freq[w])[:6]
    out = [{"point": p["point"]} for p in points]
    if terms:
        out.append({"point": "Key terms in these notes: " + ", ".join(terms)})
    return out


def quiz(text: str, max_questions: int = 5) -> list[dict]:
    """Cloze deletion: blank out an important word from a real sentence."""
    sentences = _sentences(text)
    freq = _word_freq(text)
    questions = []
    for s in sentences:
        if len(questions) >= max_questions:
            break
        words = re.findall(r"[A-Za-z][A-Za-z'’-]{3,}", s)
        candidates = [w for w in words if w.lower() in freq and len(w) >= 4]
        if not candidates:
            continue
        target = max(candidates, key=lambda w: freq.get(w.lower(), 0))
        blanked = re.sub(rf"\b{re.escape(target)}\b", "_____", s, count=1)
        questions.append({
            "question": blanked[:300],
            "answer": target,
        })
    return questions


def flashcards(text: str, max_cards: int = 8) -> list[dict]:
    """Term→definition cards from 'Term: definition' lines; fall back to top terms."""
    cards: list[dict] = []
    for ln in text.splitlines():
        m = re.match(r"^\s*([A-Za-z][A-Za-z /'’()-]{2,40})\s*[:–—-]\s+(.{10,220})\s*$", ln)
        if m and len(cards) < max_cards:
            cards.append({"front": m.group(1).strip(), "back": m.group(2).strip()})
    if not cards:
        sentences = _sentences(text)
        freq = _word_freq(text)
        for term in sorted(freq, key=lambda w: -freq[w])[:max_cards]:
            host = next((s for s in sentences if re.search(rf"\b{re.escape(term)}\b", s, re.IGNORECASE)), None)
            if host:
                cards.append({"front": term.capitalize(), "back": host[:220]})
    return cards
