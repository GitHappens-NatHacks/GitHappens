"""Small always-on-top camera window for GazeControl.

Shows the webcam (green border = face found, red = lost), the button gaze is
targeting with a dwell bar, and a red banner for problems like "Face not found".
"""

from __future__ import annotations

import numpy as np
from PySide6.QtCore import QRect, Qt, Slot
from PySide6.QtGui import QColor, QFont, QGuiApplication, QImage, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QWidget

from accessshift.modules.gaze.controller import GAZE_IGNORE

WIDTH, CAM_HEIGHT, INFO_HEIGHT = 320, 180, 74
OK = QColor(60, 200, 110)
BAD = QColor(220, 60, 60)
BG = QColor(20, 20, 24)
FG = QColor(240, 240, 240)
AMBER = QColor(255, 213, 79)


class GazeCameraPreview(QWidget):
    def __init__(self):
        super().__init__(
            None,
            Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool | Qt.WindowDoesNotAcceptFocus,
        )
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setProperty(GAZE_IGNORE, True)  # never a gaze click target
        self.setWindowTitle("Gaze camera")
        self.setFixedSize(WIDTH, CAM_HEIGHT + INFO_HEIGHT)
        self._pixmap = QPixmap()
        self._face = False
        self._target = ""
        self._dwell = 0.0
        self._error = ""

    def place_bottom_right(self, margin: int = 16) -> None:
        area = QGuiApplication.primaryScreen().availableGeometry()
        self.move(area.right() - self.width() - margin, area.bottom() - self.height() - margin)

    # --- inputs -------------------------------------------------------------------------
    @Slot(dict)
    def on_sample(self, sample: dict) -> None:
        self._face = bool(sample.get("face"))
        frame = sample.get("frame")
        if isinstance(frame, np.ndarray) and frame.ndim == 3:
            rgb = np.ascontiguousarray(frame[:, :, ::-1])  # OpenCV BGR -> RGB
            h, w = rgb.shape[:2]
            image = QImage(rgb.data, w, h, 3 * w, QImage.Format_RGB888).copy()
            self._pixmap = QPixmap.fromImage(image)
        self.update()

    def set_target_name(self, name: str) -> None:
        self._target = name
        self.update()

    @Slot(float)
    def set_dwell(self, progress: float) -> None:
        self._dwell = progress
        self.update()

    def show_error(self, text: str | None) -> None:
        self._error = text or ""
        self.update()

    # --- read back (tests) -----------------------------------------------------------------
    def frame_pixmap(self) -> QPixmap:
        return self._pixmap

    def target_text(self) -> str:
        return f"Looking at: {self._target}" if self._target else "Looking at: nothing"

    def error_text(self) -> str:
        return self._error

    # --- drawing ---------------------------------------------------------------------------
    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.fillRect(self.rect(), BG)
        cam = QRect(0, 0, WIDTH, CAM_HEIGHT)
        if not self._pixmap.isNull():
            p.drawPixmap(cam, self._pixmap.scaled(cam.size(), Qt.KeepAspectRatioByExpanding))
        p.setPen(QPen(OK if self._face else BAD, 4))
        p.drawRect(cam.adjusted(2, 2, -2, -2))

        p.setFont(QFont("Helvetica", 14, QFont.Bold))
        if self._error:
            banner = QRect(0, CAM_HEIGHT - 34, WIDTH, 34)
            p.fillRect(banner, BAD)
            p.setPen(FG)
            p.drawText(banner, Qt.AlignCenter, self._error)

        p.setPen(FG)
        p.drawText(QRect(10, CAM_HEIGHT + 6, WIDTH - 20, 26), Qt.AlignLeft | Qt.AlignVCenter, self.target_text())
        bar = QRect(10, CAM_HEIGHT + 40, WIDTH - 20, 18)
        p.setPen(QPen(FG, 1))
        p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(bar, 6, 6)
        if self._dwell > 0:
            p.setPen(Qt.NoPen)
            p.setBrush(AMBER)
            p.drawRoundedRect(QRect(bar.left(), bar.top(), int(bar.width() * self._dwell), bar.height()), 6, 6)
        p.end()
