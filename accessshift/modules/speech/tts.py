"""Offline text-to-speech via pyttsx3."""

from __future__ import annotations

import os
import subprocess
import sys
import threading


class SpeechEngine:
    def __init__(self):
        self.enabled = os.getenv("TTS_ENABLED", "1") != "0"
        self._wanted = self.enabled  # user setting, even if pyttsx3 fails to start
        self.rate = int(os.getenv("TTS_RATE", "175"))
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

    def speak_async(self, text: str) -> None:
        """Speak without blocking the UI.

        On macOS, pyttsx3 called from a background thread silently says nothing,
        so use the built-in `say` command (its own process) instead.
        """
        if not self._wanted or not text:
            return
        if sys.platform == "darwin":
            subprocess.Popen(["say", "-r", str(self.rate), text])
            return
        threading.Thread(target=self.speak, args=(text,), daemon=True).start()
