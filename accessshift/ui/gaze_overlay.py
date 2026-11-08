"""Always-on-top gaze cursor: a dot where the user looks and a ring that fills while dwelling.

Click-through: it never takes mouse input, focus, or gaze clicks.
"""

from __future__ import annotations

from PySide6.QtCore import QPoint, QRect, QRectF, Qt, Slot
from PySide6.QtGui import QColor, QFont, QGuiApplication, QPainter, QPen
from PySide6.QtWidgets import QWidget

from accessshift.modules.gaze.controller import GAZE_IGNORE

DOT_RADIUS = 12
RING_RADIUS = 22


class GazeOverlay(QWidget):
    def __init__(self, screen_rect: QRect | None = None):
        super().__init__(
            None,
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Tool
            | Qt.WindowTransparentForInput
            | Qt.WindowDoesNotAcceptFocus,
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setProperty(GAZE_IGNORE, True)
        if screen_rect is None:
            screen_rect = QGuiApplication.primaryScreen().geometry()
        self.setGeometry(screen_rect)
        self._point: QPoint | None = None
        self._dwell = 0.0
        self._target = QRect()  # targeted button, local coordinates
        self._message = ""  # red alert banner at the top of the screen

    def _ensure_screen_geometry(self) -> None:
        screen = QGuiApplication.primaryScreen()
        if screen is not None and self.geometry() != screen.geometry():
            self.setGeometry(screen.geometry())

    @Slot(QPoint)
    def set_point(self, global_point: QPoint) -> None:
        self._ensure_screen_geometry()
        self._point = self.mapFromGlobal(global_point)
        self.update()

    @Slot(float)
    def set_dwell(self, progress: float) -> None:
        self._dwell = progress
        self.update()

    @Slot(QRect)
    def set_target(self, global_rect: QRect) -> None:
        self._ensure_screen_geometry()
        if global_rect.isNull():
            self._target = QRect()
        else:
            # mapFromGlobal keeps the outline aligned when the overlay moves or DPI shifts.
            top_left = self.mapFromGlobal(global_rect.topLeft())
            self._target = QRect(top_left, global_rect.size())
        self.update()

    def set_message(self, text: str | None) -> None:
        self._message = text or ""
        self.update()

    def message(self) -> str:
        return self._message

    def clear(self) -> None:
        self._point, self._dwell, self._target, self._message = None, 0.0, QRect(), ""
        self.update()

    def paintEvent(self, _event) -> None:
        if self._point is None and self._target.isNull() and not self._message:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        if self._message:
            font = QFont("Helvetica", 22, QFont.Bold)
            p.setFont(font)
            width = p.fontMetrics().horizontalAdvance(self._message) + 60
            banner = QRect((self.width() - width) // 2, 24, width, 56)
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(200, 40, 40, 235))
            p.drawRoundedRect(banner, 14, 14)
            p.setPen(QColor(255, 255, 255))
            p.drawText(banner, Qt.AlignCenter, self._message)
        if not self._target.isNull():  # outline the button gaze will click (match gaze_style radius)
            p.setBrush(Qt.NoBrush)
            p.setPen(QPen(QColor(47, 111, 237), 4))
            p.drawRoundedRect(self._target, 18, 18)
        if self._point is None:
            p.end()
            return
        c = self._point
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(47, 111, 237, 210))
        p.drawEllipse(c, DOT_RADIUS, DOT_RADIUS)

        ring = QRectF(c.x() - RING_RADIUS, c.y() - RING_RADIUS, 2 * RING_RADIUS, 2 * RING_RADIUS)
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(QColor(90, 110, 140, 180), 3))
        p.drawEllipse(ring)
        if self._dwell > 0:
            p.setPen(QPen(QColor(11, 31, 58), 5, Qt.SolidLine, Qt.RoundCap))
            p.drawArc(ring, 90 * 16, -int(360 * 16 * self._dwell))  # clockwise from the top
        p.end()
