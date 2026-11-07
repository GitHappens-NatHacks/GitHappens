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
