import sys

from accessshift.modules.speech import tts
from accessshift.modules.speech.tts import SpeechEngine


def test_speak_async_on_mac_uses_say_without_blocking(monkeypatch):
    calls = []
    monkeypatch.setattr(sys, "platform", "darwin")
    monkeypatch.setattr(tts.subprocess, "Popen", lambda args, **kw: calls.append(args))
    monkeypatch.setenv("TTS_RATE", "180")
    engine = SpeechEngine()
    engine.speak_async("book appointment")
    assert calls == [["say", "-r", "180", "book appointment"]]


def test_speak_async_disabled_or_empty_does_nothing(monkeypatch):
    calls = []
    monkeypatch.setattr(sys, "platform", "darwin")
    monkeypatch.setattr(tts.subprocess, "Popen", lambda args, **kw: calls.append(args))
    monkeypatch.setenv("TTS_ENABLED", "0")
    SpeechEngine().speak_async("hello")
    monkeypatch.setenv("TTS_ENABLED", "1")
    SpeechEngine().speak_async("")
    assert calls == []
