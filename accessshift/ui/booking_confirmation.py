"""Green booking success popup: date/time details, Close, and auto-dismiss."""

from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QDialog, QLabel, QPushButton, QVBoxLayout


class BookingConfirmationDialog(QDialog):
    """Punchy green confirmation after a successful sample booking."""

    def __init__(
        self,
        who: str,
        visit: str,
        when: str,
        parent=None,
        auto_close_ms: int = 5000,
    ):
        super().__init__(parent)
        self.setWindowTitle("Appointment booked")
        self.setModal(True)
        self.setWindowModality(Qt.ApplicationModal)
        self.setWindowFlags(
            Qt.Dialog | Qt.WindowStaysOnTopHint | Qt.CustomizeWindowHint | Qt.WindowTitleHint
        )
        self.setMinimumSize(480, 360)
        self.setStyleSheet(
            "QDialog { background: #0F7A4A; }"
            "QLabel { color: #F4FFF8; background: transparent; }"
            "QLabel#headline { font-size: 34px; font-weight: 800; }"
            "QLabel#detail { font-size: 22px; font-weight: 650; }"
            "QLabel#hint { font-size: 14px; color: #C8F0DA; }"
            "QPushButton {"
            "  background: #F4FFF8; color: #0B3D28; font-size: 20px; font-weight: 700;"
            "  border: none; border-radius: 14px; padding: 16px 24px; min-height: 64px;"
            "}"
            "QPushButton:hover { background: #FFFFFF; }"
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(36, 36, 36, 36)
        layout.setSpacing(18)

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

        hint = QLabel("Sample booking only. Nothing was sent to a clinic.\nCloses in a few seconds, or press Close.")
        hint.setObjectName("hint")
        hint.setAlignment(Qt.AlignCenter)
        hint.setWordWrap(True)
        layout.addWidget(hint)

        close = QPushButton("Close")
        close.setDefault(True)
        close.clicked.connect(self.accept)
        layout.addWidget(close)

        if auto_close_ms > 0:
            self._timer = QTimer(self)
            self._timer.setSingleShot(True)
            self._timer.timeout.connect(self.accept)
            self._timer.start(auto_close_ms)
        else:
            self._timer = None

    def showEvent(self, event) -> None:
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
