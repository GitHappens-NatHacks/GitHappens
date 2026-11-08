"""Tint ONLY AccessShift-owned windows, never the operating-system desktop.

The old implementation created frameless, always-on-top windows for every
connected display. That could recolour unrelated apps and obscure their UI.
This one draws a low-opacity, mouse-transparent child inside registered Qt
windows. It never enumerates screens, captures input, or changes OS settings.

Public API retains ScreenTintManager for compatibility with control_center.py.
"""
from __future__ import annotations

from PySide6.QtCore import QObject, QEvent, Qt
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QWidget

TINT_COLORS = {
    'warm': '#0B1F3A',
    'cool': '#7DBBF1',
    'rose': '#B8C9DE',
}


class _LocalTint(QWidget):
    """Window-local visual film; transparent to all mouse events."""

    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.color = QColor(TINT_COLORS['warm'])
        self.opacity = 0.10
        self.setObjectName('accessshiftWindowTint')
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setGeometry(parent.rect())
        self.hide()

    def set_tint(self, color: str, opacity: int) -> None:
        self.color = QColor(TINT_COLORS.get(color, TINT_COLORS['warm']))
        self.opacity = max(0, min(20, int(opacity))) / 100.0
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        tinted = QColor(self.color)
        tinted.setAlphaF(self.opacity)
        painter.fillRect(self.rect(), tinted)
        painter.end()


class ScreenTintManager(QObject):
    """Manages overlays scoped to the AccessShift and Demo Lab windows.

    register_window() must be called explicitly for each Qt window. It never
    paints on other apps or uses any system-wide always-on-top window.
    """

    def __init__(self, app: QObject):
        super().__init__(app)
        self._app = app
        self._windows: dict[int, _LocalTint] = {}
        self._enabled = False
        self._color = 'warm'
        self._opacity = 10
        self._app.aboutToQuit.connect(self.disable)

    @property
    def active(self) -> bool:
        return self._enabled

    def register_window(self, window: QWidget) -> None:
        key = id(window)
        if key in self._windows:
            return
        tint = _LocalTint(window)
        tint.set_tint(self._color, self._opacity)
        self._windows[key] = tint
        window.installEventFilter(self)
        window.destroyed.connect(lambda _=None, k=key: self._windows.pop(k, None))
        self._sync_window(window, tint)

    def _sync_window(self, window: QWidget, tint: _LocalTint) -> None:
        tint.setGeometry(window.rect())
        if self._enabled:
            tint.show()
            tint.raise_()
        else:
            tint.hide()

    def eventFilter(self, watched, event):
        if event.type() in (QEvent.Type.Resize, QEvent.Type.Show):
            tint = self._windows.get(id(watched))
            if tint is not None:
                self._sync_window(watched, tint)
        return super().eventFilter(watched, event)

    def update(self, *, color: str, opacity: int) -> None:
        self._color = color if color in TINT_COLORS else 'warm'
        self._opacity = max(0, min(20, int(opacity)))
        for tint in list(self._windows.values()):
            tint.set_tint(self._color, self._opacity)
            if self._enabled:
                tint.raise_()

    def enable(self) -> None:
        self._enabled = True
        for tint in list(self._windows.values()):
            parent = tint.parentWidget()
            if parent is not None:
                self._sync_window(parent, tint)

    def disable(self) -> None:
        self._enabled = False
        for tint in list(self._windows.values()):
            tint.hide()
