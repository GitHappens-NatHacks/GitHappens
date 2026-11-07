"""Gaze-mode look: big, high-contrast buttons while GazeControl is on.

apply(window) saves every push button's own stylesheet and minimum height, then
enlarges them. restore(window) puts back exactly what was there before.
Colours meet WCAG AAA contrast (7:1), checked in tests.
"""

from __future__ import annotations

from PySide6.QtWidgets import QPushButton, QWidget
from shiboken6 import isValid

TEXT = "#0B1F1A"  # near-black
BUTTON_BG = "#FFFFFF"
TARGET_BG = "#FFD54F"  # amber: the button gaze is about to click (matches the overlay outline)
BUTTON_HEIGHT = 96

BUTTON_QSS = f"""
QPushButton {{
    color: {TEXT}; background: {BUTTON_BG};
    border: 3px solid {TEXT}; border-radius: 12px;
    font-size: 22px; font-weight: 700; padding: 12px 18px;
}}
QPushButton[gazeTarget="true"] {{ background: {TARGET_BG}; border: 6px solid {TEXT}; }}
QPushButton:disabled {{ color: #3A3A3A; background: #D6D6D6; border-color: #7A7A7A; }}
"""

WINDOW_QSS = """
QLabel, QCheckBox, QRadioButton { font-size: 18px; }
QLineEdit, QComboBox, QDateEdit, QSpinBox { min-height: 44px; font-size: 18px; }
"""

_SAVED = "_gaze_style_saved"
_highlighted: QPushButton | None = None


def is_applied(window: QWidget) -> bool:
    return getattr(window, _SAVED, None) is not None


def apply(window: QWidget) -> None:
    if is_applied(window):
        return
    buttons = window.findChildren(QPushButton)
    setattr(window, _SAVED, {
        "window": window.styleSheet(),
        "buttons": [(b, b.styleSheet(), b.minimumHeight()) for b in buttons],
    })
    window.setStyleSheet(window.styleSheet() + WINDOW_QSS)
    for b in buttons:
        # A button's own stylesheet beats its window's, so style each button directly.
        b.setStyleSheet(BUTTON_QSS)
        b.setMinimumHeight(max(b.minimumHeight(), BUTTON_HEIGHT))


def restore(window: QWidget) -> None:
    saved = getattr(window, _SAVED, None)
    if saved is None:
        return
    highlight(None)
    window.setStyleSheet(saved["window"])
    for b, style, min_h in saved["buttons"]:
        if isValid(b):  # skip buttons deleted while gaze mode was on
            b.setStyleSheet(style)
            b.setMinimumHeight(min_h)
    setattr(window, _SAVED, None)


def highlight(button: QPushButton | None) -> None:
    """Fill the targeted button amber (the property selector in BUTTON_QSS)."""
    global _highlighted
    for b, on in ((_highlighted, False), (button, True)):
        if b is not None and isValid(b):
            b.setProperty("gazeTarget", on)
            b.style().unpolish(b)
            b.style().polish(b)
    _highlighted = button
