from accessshift.modules.speech.tts import SpeechEngine

speaker = SpeechEngine()
print("Speech enabled:", speaker.enabled)

speaker.speak("This is the first sentence.")
speaker.wait()
speaker.speak("This is the second sentence.")
speaker.wait()
speaker.speak("And this is the third.")
speaker.wait()
print("Speech test completed.")