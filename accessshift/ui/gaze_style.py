"""Gaze-mode look: large, high-contrast targets while GazeControl is on.

apply(window) saves every push button's own stylesheet, minimum height, size policy
and layout stretch, then enlarges the buttons and lets them share the free height
(empty stretch space is collapsed). restore(window) puts back exactly what was there.
Buttons marked with property gazeChrome keep their own chrome styling.
Colours meet WCAG AAA contrast (7:1), checked in tests.
"""

from __future__ import annotations

from PySide6.QtWidgets import QBoxLayout, QPushButton, QSizePolicy, QWidget
from shiboken6 import isValid

TEXT = "#0B1F3A"  # navy ink
BUTTON_BG = "#FFFFFF"
TARGET_BG = "#D6E8F8"  # soft blue: the button gaze is about to click
BUTTON_HEIGHT = 96

BUTTON_QSS = f"""
QPushButton {{
    color: {TEXT}; background: {BUTTON_BG};
    border: 2px solid {TEXT}; border-radius: 18px;
    font-size: 22px; font-weight: 700; padding: 14px 20px;
}}
QPushButton[gazeTarget="true"] {{ background: {TARGET_BG}; border: 5px solid {TEXT}; }}
QPushButton:disabled {{ color: #5A6F8A; background: #EAF1F8; border-color: #B8C9DE; }}
"""

WINDOW_QSS = """
QLabel, QCheckBox, QRadioButton { font-size: 18px; color: #0B1F3A; }
QLineEdit, QComboBox, QDateEdit, QSpinBox { min-height: 44px; font-size: 18px; }
"""

_SAVED = "_gaze_style_saved"
_highlighted: QPushButton | None = None


def is_applied(window: QWidget) -> bool:
    return getattr(window, _SAVED, None) is not None


def apply(window: QWidget) -> None:
    if is_applied(window):
        return
    buttons = [
        b for b in window.findChildren(QPushButton)
        if not bool(b.property('gazeChrome'))
    ]
    saved = {
        "window": window.styleSheet(),
        "buttons": [(b, b.styleSheet(), b.minimumHeight(), QSizePolicy(b.sizePolicy())) for b in buttons],
        "stretch": [],  # (layout, index, original stretch)
    }
    setattr(window, _SAVED, saved)
    window.setStyleSheet(window.styleSheet() + WINDOW_QSS)
    for b in buttons:
        # A button's own stylesheet beats its window's, so style each button directly.
        b.setStyleSheet(BUTTON_QSS)
        b.setMinimumHeight(max(b.minimumHeight(), BUTTON_HEIGHT))
    _stretch_buttons(buttons, saved["stretch"])


def restore(window: QWidget) -> None:
    saved = getattr(window, _SAVED, None)
    if saved is None:
        return
    highlight(None)
    window.setStyleSheet(saved["window"])
    for layout, index, stretch in saved["stretch"]:
        if isValid(layout) and index < layout.count():
            layout.setStretch(index, stretch)
    for b, style, min_h, policy in saved["buttons"]:
        if isValid(b):  # skip buttons deleted while gaze mode was on
            b.setStyleSheet(style)
            b.setMinimumHeight(min_h)
            b.setSizePolicy(policy)
    setattr(window, _SAVED, None)


def _stretch_buttons(buttons: list[QPushButton], saved: list) -> None:
    """In vertical layouts, give buttons the free height and take it from empty stretch."""
    seen = set()
    for b in buttons:
        parent = b.parentWidget()
        layout = parent.layout() if parent is not None else None
        if not isinstance(layout, QBoxLayout) or layout.direction() not in (
            QBoxLayout.TopToBottom, QBoxLayout.BottomToTop
        ):
            continue
        if id(layout) not in seen:
            seen.add(id(layout))
            for i in range(layout.count()):
                if layout.itemAt(i).spacerItem() is not None and layout.stretch(i) > 0:
                    saved.append((layout, i, layout.stretch(i)))
                    layout.setStretch(i, 0)
        i = layout.indexOf(b)
        if i >= 0:
            saved.append((layout, i, layout.stretch(i)))
            layout.setStretch(i, 1)
            b.setSizePolicy(b.sizePolicy().horizontalPolicy(), QSizePolicy.Expanding)


def highlight(button: QPushButton | None) -> None:
    """Fill the targeted button soft blue (the property selector in BUTTON_QSS)."""
    global _highlighted
    for b, on in ((_highlighted, False), (button, True)):
        if b is not None and isValid(b):
            b.setProperty("gazeTarget", on)
            b.style().unpolish(b)
            b.style().polish(b)
            b.update()
    _highlighted = button
