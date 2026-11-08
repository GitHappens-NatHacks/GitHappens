from accessshift.modules.speech.tts import SpeechEngine

speaker = SpeechEngine()
print("Speech enabled:", speaker.enabled)
speaker.speak("Welcome to AccessShift AI. Your speech assistant is working.")
speaker.wait()
print("Speech test completed.")