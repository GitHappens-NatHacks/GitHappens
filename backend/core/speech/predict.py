"""Text prediction. Rule-based (offline). Optional ONNX hook for later."""
from __future__ import annotations

import os
from pathlib import Path

_LEXICON = [
    "appointment", "doctor", "tomorrow", "morning", "afternoon", "follow-up",
    "prescription", "insurance", "neurology", "cardiology", "help", "yes",
    "no", "confirm", "cancel",
]

_PHRASES = [
    "I need an appointment",
    "I need an appointment with my doctor",
    "I need help booking an appointment",
    "I want to cancel my appointment",
    "I want to reschedule my appointment",
    "I want to confirm my appointment",
    "I need to refill my prescription",
    "I would like to speak to a doctor",
    "I am experiencing pain",
    "I need help understanding my medication",
    "Please contact me tomorrow",
]


def _onnx_rerank(prefix: str, candidates: list[str]) -> list[str] | None:
    model_path = os.getenv("ONNX_MODEL_PATH", "")
    if not model_path or not Path(model_path).exists():
        return None
    try:
        import onnxruntime as ort  # noqa: F401

        return candidates  # TODO: real inference once a model is chosen
    except Exception:
        return None


def suggest_words(text: str, limit: int = 5) -> list[str]:
    text = text or ""
    last = text.rsplit(" ", 1)[-1].lower().strip()
    if not last or text.endswith(" "):
        return _LEXICON[:limit]
    hits = [w for w in _LEXICON if w.startswith(last) and w != last]
    if os.getenv("PREDICTION_ENABLED", "0") == "1":
        hits = _onnx_rerank(last, hits) or hits
    return hits[:limit]


def suggest_phrases(text: str, limit: int = 5) -> list[str]:
    t = (text or "").lower().strip()
    if not t:
        return _PHRASES[:limit]
    starts = [p for p in _PHRASES if p.lower().startswith(t)]
    contains = [p for p in _PHRASES if t in p.lower() and p not in starts]
    return (starts + contains)[:limit] or _PHRASES[:limit]


def suggest(text: str, limit: int = 5) -> list[str]:
    """Single entry point for the UI: phrases first, then word completions."""
    phrases = suggest_phrases(text, limit)
    words = suggest_words(text, limit) if (text or "").strip() else []
    return list(dict.fromkeys(phrases + words))[:limit]