"""SpeechPanel: text box + big suggestion buttons + Speak/Clear."""
from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QHBoxLayout, QLineEdit, QPushButton, QVBoxLayout, QWidget,
)

from .predict import suggest
from .tts import SpeechEngine

N_SUGGESTIONS = 5


class SpeechPanel(QWidget):
    spoken = Signal(str)  # emitted when the user speaks a phrase (for metrics)

    def __init__(self, speaker: SpeechEngine | None = None, parent=None):
        super().__init__(parent)
        self.speaker = speaker or SpeechEngine()

        big = QFont()
        big.setPointSize(18)

        self.input = QLineEdit()
        self.input.setPlaceholderText("Type or pick a phrase...")
        self.input.setFont(big)
        self.input.setMinimumHeight(60)

        self.buttons: list[QPushButton] = []
        suggestions_col = QVBoxLayout()
        for _ in range(N_SUGGESTIONS):
            b = QPushButton()
            b.setFont(big)
            b.setMinimumHeight(64)
            b.clicked.connect(lambda _=False, btn=b: self._apply(btn.text()))
            self.buttons.append(b)
            suggestions_col.addWidget(b)

        self.speak_btn = QPushButton("Speak")
        self.clear_btn = QPushButton("Clear")
        for b in (self.speak_btn, self.clear_btn):
            b.setFont(big)
            b.setMinimumHeight(72)
        self.speak_btn.clicked.connect(self.speak_current)
        self.clear_btn.clicked.connect(self.input.clear)

        actions = QHBoxLayout()
        actions.addWidget(self.speak_btn, 2)
        actions.addWidget(self.clear_btn, 1)

        layout = QVBoxLayout(self)
        layout.addWidget(self.input)
        layout.addLayout(suggestions_col)
        layout.addLayout(actions)

        self.input.textChanged.connect(self.refresh)
        self.input.returnPressed.connect(self.speak_current)
        self.refresh("")

    def refresh(self, text: str) -> None:
        options = suggest(text, N_SUGGESTIONS)
        for i, btn in enumerate(self.buttons):
            if i < len(options):
                btn.setText(options[i])
                btn.setVisible(True)
            else:
                btn.setVisible(False)

    def _apply(self, choice: str) -> None:
        text = self.input.text()
        if " " in choice or not text.strip():
            new = choice                                  # full phrase
        elif text.endswith(" "):
            new = text + choice + " "                     # next word
        else:
            new = text.rsplit(" ", 1)[0] + " " if " " in text else ""
            new += choice + " "                           # complete last word
        self.input.setText(new)
        self.input.setFocus()

    def speak_current(self) -> None:
        text = self.input.text().strip()
        if text:
            self.speaker.speak(text)
            self.spoken.emit(text)