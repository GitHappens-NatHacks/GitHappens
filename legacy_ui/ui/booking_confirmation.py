"""Green booking success popup: details, then Start over or Close.

choice is "start_over" (book another, no recalibration) or "close" (leave hands-free).
No auto-close by default: the person chooses.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QPushButton, QVBoxLayout


class BookingConfirmationDialog(QDialog):
    """Punchy green confirmation after a successful sample booking."""

    def __init__(
        self,
        who: str,
        visit: str,
        when: str,
        parent=None,
        auto_close_ms: int = 0,
        full_window: bool = False,
    ):
        super().__init__(parent)
        self.choice = "close"
        self._full_window = full_window and parent is not None  # covers the parent: its own screen
        self.setWindowTitle("Appointment booked")
        self.setModal(True)
        self.setWindowModality(Qt.ApplicationModal)
        self.setWindowFlags(
            Qt.Dialog | Qt.WindowStaysOnTopHint | Qt.CustomizeWindowHint | Qt.WindowTitleHint
        )
        self.setMinimumSize(480, 360)
        if self._full_window:
            self.setWindowFlags(Qt.Dialog | Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint)
        scale = 1.6 if self._full_window else 1.0
        px = lambda n: f"{round(n * scale)}px"  # noqa: E731
        button_h = 140 if self._full_window else 64
        self.setStyleSheet(
            "QDialog { background: #0F7A4A; }"
            "QLabel { color: #F4FFF8; background: transparent; }"
            f"QLabel#headline {{ font-size: {px(34)}; font-weight: 800; }}"
            f"QLabel#detail {{ font-size: {px(22)}; font-weight: 650; }}"
            f"QLabel#hint {{ font-size: {px(14)}; color: #C8F0DA; }}"
            "QPushButton {"
            f"  background: #F4FFF8; color: #0B3D28; font-size: {px(20)}; font-weight: 700;"
            f"  border: none; border-radius: 14px; padding: 16px 24px; min-height: {button_h}px;"
            "}"
            "QPushButton:hover { background: #FFFFFF; }"
        )

        layout = QVBoxLayout(self)
        if self._full_window:  # bottom space keeps the buttons clear of the camera preview
            layout.setContentsMargins(80, 60, 80, 290)
        else:
            layout.setContentsMargins(36, 36, 36, 36)
        layout.setSpacing(28 if self._full_window else 18)

        headline = QLabel("You're booked!")
        headline.setObjectName("headline")
        headline.setAlignment(Qt.AlignCenter)
        layout.addWidget(headline)

        detail = QLabel(
            f"{visit}\n"
            f"for {who}\n"
            f"{when}"
        )
        detail.setObjectName("detail")
        detail.setAlignment(Qt.AlignCenter)
        detail.setWordWrap(True)
        layout.addWidget(detail)

        hint = QLabel(
            "Start over to book another, or Close to leave hands-free control."
        )
        hint.setObjectName("hint")
        hint.setAlignment(Qt.AlignCenter)
        hint.setWordWrap(True)
        layout.addWidget(hint)

        row = QHBoxLayout()
        row.setSpacing(32 if self._full_window else 16)
        start_over = QPushButton("Start over")
        start_over.clicked.connect(lambda: self._choose("start_over"))
        close = QPushButton("Close")
        close.setDefault(True)
        close.clicked.connect(lambda: self._choose("close"))
        for b in (start_over, close):
            b.setMinimumHeight(button_h)
            row.addWidget(b)
        layout.addLayout(row)

        if auto_close_ms > 0:
            self._timer = QTimer(self)
            self._timer.setSingleShot(True)
            self._timer.timeout.connect(self.accept)
            self._timer.start(auto_close_ms)
        else:
            self._timer = None

    def _choose(self, choice: str) -> None:
        self.choice = choice
        self.accept()

    def showEvent(self, event) -> None:
        if self._full_window and self.parentWidget() is not None:
            self.setGeometry(self.parentWidget().window().geometry())
        super().showEvent(event)
        self.raise_()
        self.activateWindow()

    def reject(self) -> None:
        if self._timer is not None:
            self._timer.stop()
        super().reject()

    def accept(self) -> None:
        if self._timer is not None:
            self._timer.stop()
        super().accept()
