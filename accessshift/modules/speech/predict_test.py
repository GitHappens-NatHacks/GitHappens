from accessshift.modules.speech.predict import (
    suggest_words,
    suggest_phrases
)

print("\n--- Healthcare Phrase Predictions ---")

test_inputs = [
    "appointment",
    "prescription",
    "doctor",
    "pain",
]

for text in test_inputs:
    print(f"\nInput: {text}")
    print("Suggestions:", suggest_phrases(text))