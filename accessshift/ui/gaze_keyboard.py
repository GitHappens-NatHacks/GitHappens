"""Eye-typing keyboard: big keys, word suggestions, and Speak (text-to-speech).

Every key is a normal QPushButton, so GazeController clicks it by dwell or blink.
Key size follows gaze accuracy (min_target_px), so less accurate tracking gets bigger keys.
"""

from __future__ import annotations

from PySide6.QtGui import QFont
from PySide6.QtWidgets import QGridLayout, QHBoxLayout, QLineEdit, QPushButton, QVBoxLayout, QWidget

from accessshift.modules.gaze.dwell import min_target_px
from accessshift.modules.speech.predict import suggest_words

LETTER_ROWS = ["ABCDEFG", "HIJKLMN", "OPQRSTU", "VWXYZ"]
SUGGESTIONS = 5


class GazeKeyboard(QWidget):
    def __init__(self, speech, error_px: float = 0.0, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Gaze keyboard")
        self._speech = speech
        size = min_target_px(error_px)
        key_font = QFont("Helvetica", max(16, size // 4), QFont.Bold)

        def make(label: str, handler) -> QPushButton:
            b = QPushButton(label)
            b.setMinimumSize(size, size)
            b.setFont(key_font)
            b.clicked.connect(handler)
            return b

        self.display = QLineEdit()
        self.display.setReadOnly(True)
        self.display.setFont(QFont("Helvetica", 28))
        self.display.setMinimumHeight(size)
        self.display.textChanged.connect(self._refresh_suggestions)

        self.suggestion_buttons = [make("", lambda _=False, i=i: self._choose(i)) for i in range(SUGGESTIONS)]
        sugg_row = QHBoxLayout()
        for b in self.suggestion_buttons:
            sugg_row.addWidget(b)

        self.key_buttons: dict[str, QPushButton] = {}
        grid = QGridLayout()
        for r, row in enumerate(LETTER_ROWS):
            for c, ch in enumerate(row):
                self.key_buttons[ch] = make(ch, lambda _=False, ch=ch: self._type(ch.lower()))
                grid.addWidget(self.key_buttons[ch], r, c)

        actions = QHBoxLayout()
        for label, handler in (
            ("Space", lambda: self._type(" ")),
            ("⌫", self._backspace),
            ("Clear", lambda: self.set_text("")),
            ("Speak", self._speak),
        ):
            self.key_buttons[label] = make(label, handler)
            actions.addWidget(self.key_buttons[label])

        layout = QVBoxLayout(self)
        layout.addWidget(self.display)
        layout.addLayout(sugg_row)
        layout.addLayout(grid)
        layout.addLayout(actions)
        self._refresh_suggestions()

    # --- text ------------------------------------------------------------------------
    def text(self) -> str:
        return self.display.text()

    def set_text(self, text: str) -> None:
        self.display.setText(text)

    def _current_word(self) -> str:
        return self.text().split(" ")[-1]

    def _type(self, s: str) -> None:
        self.set_text(self.text() + s)

    def _backspace(self) -> None:
        self.set_text(self.text()[:-1])

    def _choose(self, i: int) -> None:
        word = self.suggestion_buttons[i].text()
        if not word:
            return
        current = self._current_word()
        self.set_text(self.text()[: len(self.text()) - len(current)] + word + " ")

    def _refresh_suggestions(self) -> None:
        words = suggest_words(self._current_word(), SUGGESTIONS)
        for i, b in enumerate(self.suggestion_buttons):
            word = words[i] if i < len(words) else ""
            b.setText(word)
            b.setEnabled(bool(word))

    # --- speech ----------------------------------------------------------------------
    def _speak(self) -> None:
        text = self.text().strip()
        if not text:
            return
        self._speech.speak_async(text)  # non-blocking, so gaze keeps working while it talks
