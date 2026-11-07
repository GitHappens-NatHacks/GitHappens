"""Text prediction hooks.

Rule-based suggestions work offline. Optional ONNX path reads ONNX_MODEL_PATH
when PREDICTION_ENABLED=1.
"""

from __future__ import annotations

import os
from pathlib import Path

# Healthcare-demo lexicon for fast offline suggestions
_LEXICON = [
    "appointment",
    "doctor",
    "tomorrow",
    "morning",
    "afternoon",
    "follow-up",
    "prescription",
    "insurance",
    "neurology",
    "cardiology",
    "help",
    "yes",
    "no",
    "confirm",
    "cancel",
]


def suggest_words(prefix: str, limit: int = 5) -> list[str]:
    prefix = (prefix or "").lower().strip()
    if not prefix:
        return _LEXICON[:limit]
    hits = [w for w in _LEXICON if w.startswith(prefix)]
    if os.getenv("PREDICTION_ENABLED", "0") == "1":
        hits = _onnx_rerank(prefix, hits) or hits
    return hits[:limit]


def _onnx_rerank(prefix: str, candidates: list[str]) -> list[str] | None:
    model_path = os.getenv("ONNX_MODEL_PATH", "")
    if not model_path or not Path(model_path).exists():
        return None
    try:
        import onnxruntime as ort  # noqa: F401

        # Model-specific inference belongs here once a model is chosen.
        return candidates
    except Exception:
        return None

# Healthcare phrase suggestions

_PHRASES = [
    "I need an appointment",
    "I need an appointment with my doctor",
    "I need help booking an appointment",
    "I want to cancel my appointment",
    "I want to reschedule my appointment",
    "I need to refill my prescription",
    "I would like to speak to a doctor",
    "I am experiencing pain",
    "I need help understanding my medication",
    "I want to confirm my appointment",
    "Please contact me tomorrow",
]


def suggest_phrases(text: str, limit: int = 5) -> list[str]:
    text = (text or "").lower().strip()

    if not text:
        return _PHRASES[:limit]

    return [
        phrase for phrase in _PHRASES
        if text in phrase.lower()
    ][:limit]
