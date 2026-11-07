"""Optional low-opacity, click-through desktop colour tint.

This is an overlay, NOT a universal colour-profile, contrast or font replacement.
It is explicitly activated by the user, never auto-starts, and is removed when
AccessShift closes. Platform window managers may limit always-on-top overlays.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QGuiApplication, QPainter
from PySide6.QtWidgets import QWidget

TINT_COLORS = {
    'warm': '#F7BE73',
    'cool': '#7DBBF1',
    'rose': '#F9B0D2',
}


class _TintWindow(QWidget):
    def __init__(self, screen, color: str, opacity: int):
        flags = (Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint |
                 Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.WindowDoesNotAcceptFocus |
                 Qt.WindowType.WindowTransparentForInput)
        super().__init__(None, flags)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._color = QColor(color)
        self._opacity = opacity
        self.setGeometry(screen.geometry())
        self.setObjectName('desktopColorTint')
        self.show()

    def paintEvent(self, event):
        painter = QPainter(self)
        color = QColor(self._color)
        color.setAlphaF(max(0.0, min(0.28, self._opacity / 100.0)))
        painter.fillRect(self.rect(), color)
        painter.end()


class ScreenTintManager:
    """Owns one click-through tint window per display; no on-disk active state."""

    def __init__(self, app: QGuiApplication):
        self._app = app
        self._windows: list[_TintWindow] = []
        self._enabled = False
        self._color = 'warm'
        self._opacity = 15
        self._app.screenAdded.connect(self._screens_changed)
        self._app.screenRemoved.connect(self._screens_changed)
        self._app.aboutToQuit.connect(self.disable)

    @property
    def active(self) -> bool:
        return self._enabled

    def update(self, *, color: str, opacity: int) -> None:
        self._color = color if color in TINT_COLORS else 'warm'
        self._opacity = max(5, min(28, int(opacity)))
        if self._enabled:
            self._make_windows()

    def enable(self) -> None:
        self._enabled = True
        self._make_windows()

    def disable(self) -> None:
        self._enabled = False
        self._close_windows()

    def _close_windows(self) -> None:
        for window in self._windows:
            window.close()
            window.deleteLater()
        self._windows.clear()

    def _screens_changed(self, *args) -> None:
        if self._enabled:
            self._make_windows()

    def _make_windows(self) -> None:
        self._close_windows()
        for screen in self._app.screens():
            self._windows.append(_TintWindow(screen, TINT_COLORS[self._color], self._opacity))
