"""Navy booking success popup: date/time details, Close, and auto-dismiss."""

from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QDialog, QLabel, QPushButton, QVBoxLayout


class BookingConfirmationDialog(QDialog):
    """Confirmation after a successful sample booking, matched to Control Center navy/blue."""

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
            "QDialog { background: #0B1F3A; }"
            "QLabel { color: #F4F7FB; background: transparent; }"
            "QLabel#headline { font-size: 34px; font-weight: 200; letter-spacing: -0.6px; }"
            "QLabel#detail { font-size: 20px; font-weight: 500; color: #D6E8F8; }"
            "QLabel#hint { font-size: 14px; color: #8A9BB0; }"
            "QPushButton {"
            "  background: #2F6FED; color: #FFFFFF; font-size: 18px; font-weight: 650;"
            "  border: none; border-radius: 12px; padding: 16px 24px; min-height: 56px;"
            "}"
            "QPushButton:hover { background: #1E5AD6; }"
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(48, 48, 48, 48)
        layout.setSpacing(22)

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
