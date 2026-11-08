"""Live visual-accessibility preview and local application-wide appearance.

Qt controls can change styles in applications they own. This module does not
claim to rewrite fonts/colors inside arbitrary third-party applications.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from PySide6.QtGui import QFont
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout


@dataclass(frozen=True)
class Palette:
    background: str
    panel: str
    surface: str
    foreground: str
    muted: str
    border: str
    accent: str
    accent_text: str


PALETTES: dict[str, Palette] = {
    'standard': Palette(
        '#F5F5F7', '#FFFFFF', '#EAF1F8', '#0B1F3A', '#3E5370',
        '#D7E0EC', '#0B1F3A', '#FFFFFF',
    ),
    'high_contrast': Palette(
        '#050B16', '#0B1F3A', '#123A6D', '#F4F7FB', '#C5D8F5',
        '#2F6FED', '#2F6FED', '#050B16',
    ),
    'warm': Palette(
        '#F5F5F7', '#FFFFFF', '#EAF1F8', '#0B1F3A', '#3E5370',
        '#B8C9DE', '#123A6D', '#FFFFFF',
    ),
    'cool': Palette(
        '#EAF4FF', '#FFFFFF', '#DCEFFF', '#0B1F3A', '#3E5370',
        '#B8D4F0', '#123A6D', '#FFFFFF',
    ),
}


def _font_size(percentage: int, base: int) -> int:
    return max(10, round(base * max(90, min(160, int(percentage))) / 100))


def scaled_stylesheet(base_qss: str, font_size_pct: int) -> str:
    """Scale content typography without blowing up chrome navigation."""
    pct = max(90, min(160, int(font_size_pct)))
    fixed = (
        '#navButton', '#brandMark', '#brandDot', '#topBarBadge',
        '#goodPill', '#footerText', '#moduleCellTitle', '#moduleCellStatus',
    )

    def update_rule(match: re.Match[str]) -> str:
        selector, body = match.group(1), match.group(2)
        if any(n in selector for n in fixed):
            return match.group(0)
        new = re.sub(
            r'font-size\s*:\s*(\d+)px',
            lambda m: f'font-size: {max(10, round(int(m.group(1)) * pct / 100))}px',
            body,
        )
        return selector + '{' + new + '}'

    return re.sub(r'([^{}]+)\{([^{}]*)\}', update_rule, base_qss)


def theme_override(profile: str) -> str:
    """Themed content surfaces; site header stays on paper chrome."""
    if profile == 'standard':
        return ''
    p = PALETTES.get(profile, PALETTES['standard'])
    return f'''
    QWidget#appRoot, QWidget#scrollContent {{ background: {p.background}; color: {p.foreground}; }}
    QFrame#siteHeader, QFrame#footerBar {{ background: {p.panel}; border-color: {p.border}; }}
    QFrame#card, QFrame#optionCard, QFrame#hero {{ background: {p.panel}; border-color: {p.border}; }}
    QFrame#innerCard {{ background: {p.surface}; border-color: {p.border}; }}
    QLabel#pageTitle, QLabel#sectionTitle, QLabel#cardTitle, QLabel#number,
    QLabel#bodyText, QLabel#heroTitle, QLabel#brandMark {{ color: {p.foreground}; }}
    QLabel#pageDescription, QLabel#subtle, QLabel#micro, QLabel#heroDescription,
    QLabel#footerText {{ color: {p.muted}; }}
    QLabel#pill {{ background: {p.surface}; color: {p.foreground}; }}
    QPushButton#secondaryButton, QPushButton#presetButton {{
        background: {p.panel}; color: {p.foreground}; border-color: {p.border};
    }}
    QPushButton#presetButton:checked {{ background: #D6E8F8; border-color: {p.foreground}; color: {p.foreground}; }}
    QPushButton#primaryButton, QPushButton#heroButton {{
        background: {p.accent}; color: {p.accent_text}; border-color: {p.accent};
    }}
    QLineEdit, QTextEdit, QComboBox {{ background: {p.panel}; color: {p.foreground}; border-color: {p.border}; }}
    QComboBox QAbstractItemView {{ background: {p.panel}; color: {p.foreground}; }}
    '''


def apply_accessshift_appearance(window: Any, base_qss: str, font_size_pct: int, color_profile: str) -> None:
    """Apply a user's preferences to the AccessShift window itself, immediately."""
    window.setStyleSheet(scaled_stylesheet(base_qss, font_size_pct) + theme_override(color_profile))


class VisualPreview(QFrame):
    """A working, independently styled preview of text, contrast and spacing."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName('smartPreview')
        self.setMinimumHeight(200)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(23, 22, 23, 22)
        lay.setSpacing(10)
        self.heading = QLabel('Your screen, your comfort.')
        self.heading.setAccessibleName('Preview heading')
        self.body = QLabel(
            'Make text easier to read with size, spacing and contrast adjustments.\n'
            'This live preview updates as you move the controls.',
        )
        self.body.setWordWrap(True)
        self.note = QLabel('Changes affect AccessShift and the local healthcare demo only.')
        self.note.setWordWrap(True)
        self.action = QPushButton('Try sample button')
        self.action.setAccessibleName('Try sample button in preview')
        self.action.setMinimumHeight(42)
        self.action.clicked.connect(self._pressed)
        action_lay = QHBoxLayout()
        action_lay.addWidget(self.action)
        action_lay.addStretch()
        lay.addWidget(self.heading)
        lay.addWidget(self.body)
        lay.addLayout(action_lay)
        lay.addWidget(self.note)
        lay.addStretch(1)
        self.set_preferences(110, 'standard', 0)

    def _pressed(self):
        self.note.setText('Selected successfully. This sample button is interactive.')

    def set_preferences(self, font_size_pct: int, color_profile: str, letter_spacing_px: int) -> None:
        p = PALETTES.get(color_profile, PALETTES['standard'])
        self.setStyleSheet(
            f'QFrame#smartPreview {{ background-color: {p.background}; '
            f'border: 1px solid {p.border}; border-radius: 15px; }}',
        )
        for widget, pt, weight, color in [
            (self.heading, 19, QFont.Weight.Bold, p.foreground),
            (self.body, 13, QFont.Weight.Normal, p.foreground),
            (self.note, 11, QFont.Weight.Normal, p.muted),
        ]:
            font = QFont(widget.font())
            font.setPixelSize(_font_size(font_size_pct, pt))
            font.setWeight(weight)
            font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, max(0, min(4, int(letter_spacing_px))))
            widget.setFont(font)
            widget.setStyleSheet(f'color: {color}; background: transparent; border: none;')
        self.action.setStyleSheet(
            f'QPushButton {{ background: {p.accent}; color: {p.accent_text}; '
            'padding: 10px 16px; border: none; border-radius: 9px; font-weight: 700; }',
        )
        action_font = QFont(self.action.font())
        action_font.setPixelSize(_font_size(font_size_pct, 12))
        self.action.setFont(action_font)
