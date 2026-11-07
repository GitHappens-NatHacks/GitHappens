"""Offline text-to-speech. Never blocks the UI thread."""
from __future__ import annotations

import queue
import shutil
import subprocess
import sys
import threading


class SpeechEngine:
    """Speaks text on a worker thread.

    - macOS: uses the built-in `say` command.
    - Windows/Linux: uses pyttsx3 (a fresh engine per phrase, because a
      reused engine often goes silent after the first phrase on Windows).
    """

    def __init__(self, rate: int = 170, volume: float = 1.0):
        self.rate = rate
        self.volume = volume
        self.enabled = False
        self._q: queue.Queue[str | None] = queue.Queue()
        self._proc: subprocess.Popen | None = None
        self._use_say = sys.platform == "darwin"
        self._ready = threading.Event()

        threading.Thread(target=self._run, daemon=True).start()
        self._ready.wait(timeout=5)

    def _make_engine(self):
        import pyttsx3

        engine = pyttsx3.init()
        engine.setProperty("rate", self.rate)
        engine.setProperty("volume", self.volume)
        return engine

    def _run(self) -> None:
        try:
            if self._use_say:
                self.enabled = shutil.which("say") is not None
            else:
                self._make_engine()  # just to check that it works
                self.enabled = True
        except Exception as e:
            print("TTS init failed:", e)
            self.enabled = False
        finally:
            self._ready.set()

        while True:
            text = self._q.get()
            try:
                if text is None:
                    return
                if not self.enabled:
                    continue
                if self._use_say:
                    self._proc = subprocess.Popen(["say", "-r", str(self.rate), text])
                    self._proc.wait()
                else:
                    engine = self._make_engine()
                    engine.say(text)
                    engine.runAndWait()
                    engine.stop()
                    del engine
            except Exception as e:
                print("TTS error:", e)
            finally:
                self._q.task_done()

    def speak(self, text: str, interrupt: bool = True) -> None:
        text = (text or "").strip()
        if not text or not self.enabled:
            return
        if interrupt:
            self._drain()
            if self._proc and self._proc.poll() is None:
                self._proc.terminate()
        self._q.put(text)

    def wait(self) -> None:
        self._q.join()

    def close(self) -> None:
        self._drain()
        self._q.put(None)

    def _drain(self) -> None:
        while True:
            try:
                self._q.get_nowait()
                self._q.task_done()
            except queue.Empty:
                break