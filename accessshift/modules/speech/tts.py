"""Offline text-to-speech via pyttsx3."""

from __future__ import annotations

import os


class SpeechEngine:
    def __init__(self):
        self.enabled = os.getenv("TTS_ENABLED", "1") != "0"
        self._engine = None
        if self.enabled:
            try:
                import pyttsx3

                self._engine = pyttsx3.init()
                rate = int(os.getenv("TTS_RATE", "175"))
                self._engine.setProperty("rate", rate)
            except Exception:
                self._engine = None
                self.enabled = False

    def speak(self, text: str) -> None:
        if not self.enabled or not self._engine or not text:
            return
        self._engine.say(text)
        self._engine.runAndWait()
