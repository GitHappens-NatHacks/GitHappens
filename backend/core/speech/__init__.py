"""Offline speech synthesis and word/phrase prediction."""

from backend.core.speech.predict import suggest, suggest_phrases, suggest_words
from backend.core.speech.tts import SpeechEngine

__all__ = [
    "SpeechEngine",
    "suggest",
    "suggest_phrases",
    "suggest_words",
]
