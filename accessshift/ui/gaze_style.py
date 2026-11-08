"""Gaze-mode look: big, high-contrast buttons while GazeControl is on.

apply(window) saves every push button's own stylesheet, minimum height, size policy
and layout stretch, then enlarges the buttons and lets them share the free height
(empty stretch space is collapsed). restore(window) puts back exactly what was there.
Colours meet WCAG AAA contrast (7:1), checked in tests.
"""

from __future__ import annotations

from PySide6.QtWidgets import QBoxLayout, QPushButton, QSizePolicy, QWidget
from shiboken6 import isValid

TEXT = "#0B1F1A"  # near-black
BUTTON_BG = "#FFFFFF"
TARGET_BG = "#FFD54F"  # amber: the button gaze is about to click (matches the overlay outline)
BUTTON_HEIGHT = 96

OWN_STYLE = "gazeOwnStyle"  # widgets with this property set style themselves (e.g. grid squares)


def button_qss(palette=None, font_px: int = 22) -> str:
    """Big-button style. With an app Palette, uses the app's colours (text, panel, accent)."""
    if palette is None:
        text, bg, target, target_text = TEXT, BUTTON_BG, TARGET_BG, TEXT
    else:
        text, bg, target, target_text = palette.foreground, palette.panel, palette.accent, palette.accent_text
    return f"""
QPushButton {{
    color: {text}; background: {bg};
    border: 3px solid {text}; border-radius: 14px;
    font-size: {font_px}px; font-weight: 700; padding: 12px 18px;
}}
QPushButton[gazeTarget="true"] {{ color: {target_text}; background: {target}; border: 6px solid {text}; }}
QPushButton:disabled {{ color: #3A3A3A; background: #D6D6D6; border-color: #7A7A7A; }}
"""


BUTTON_QSS = button_qss()

WINDOW_QSS = """
QLabel, QCheckBox, QRadioButton { font-size: 18px; }
QLineEdit, QComboBox, QDateEdit, QSpinBox { min-height: 44px; font-size: 18px; }
"""

_SAVED = "_gaze_style_saved"
_highlighted: QPushButton | None = None


def is_applied(window: QWidget) -> bool:
    return getattr(window, _SAVED, None) is not None


def apply(window: QWidget, palette=None) -> None:
    if is_applied(window):
        return
    buttons = [b for b in window.findChildren(QPushButton) if not b.property(OWN_STYLE)]
    saved = {
        "window": window.styleSheet(),
        "buttons": [(b, b.styleSheet(), b.minimumHeight(), QSizePolicy(b.sizePolicy())) for b in buttons],
        "stretch": [],  # (layout, index, original stretch)
    }
    setattr(window, _SAVED, saved)
    window.setStyleSheet(window.styleSheet() + WINDOW_QSS)
    for b in buttons:
        # A button's own stylesheet beats its window's, so style each button directly.
        b.setStyleSheet(button_qss(palette))
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
    """Fill the targeted button amber (the property selector in BUTTON_QSS)."""
    global _highlighted
    for b, on in ((_highlighted, False), (button, True)):
        if b is not None and isValid(b):
            b.setProperty("gazeTarget", on)
            b.style().unpolish(b)
            b.style().polish(b)
    _highlighted = button
