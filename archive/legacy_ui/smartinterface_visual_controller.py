"""Live visual-accessibility preview and local application-wide appearance.

Qt controls can change styles in applications they own. This module does not
claim to rewrite fonts/colors inside arbitrary third-party applications.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from PySide6.QtCore import Qt
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
    'standard': Palette('#F5F7FC', '#FFFFFF', '#F8F9FF', '#1D2941', '#64718B', '#E4E8F3', '#6347E9', '#FFFFFF'),
    'high_contrast': Palette('#090E1C', '#111827', '#192438', '#FFFFFF', '#E4ECF7', '#D3DEFC', '#FFD84D', '#101010'),
    'warm': Palette('#FFF7E9', '#FFFEFA', '#FFF1D9', '#332718', '#6B563B', '#E9D3B4', '#9159CB', '#FFFFFF'),
    'cool': Palette('#ECF6FF', '#FFFFFF', '#DCEFFF', '#152C45', '#486784', '#B9D8F4', '#255FD3', '#FFFFFF'),
}


def _font_size(percentage: int, base: int) -> int:
    return max(10, round(base * max(90, min(160, int(percentage))) / 100))


def scaled_stylesheet(base_qss: str, font_size_pct: int) -> str:
    """Scale content typography without making navigation/sidebar overflow."""
    pct = max(90, min(160, int(font_size_pct)))
    fixed = ('#navButton', '#sideSection', '#brandName', '#brandSub',
             '#sidebarFoot', '#logoMark', '#topBarTitle', '#topBarBadge',
             '#heroEyebrow', '#goodPill', '#footerText')

    def update_rule(match: re.Match[str]) -> str:
        selector, body = match.group(1), match.group(2)
        if any(n in selector for n in fixed):
            return match.group(0)
        new = re.sub(r'font-size\s*:\s*(\d+)px',
                     lambda m: f'font-size: {max(10, round(int(m.group(1)) * pct / 100))}px',
                     body)
        return selector + '{' + new + '}'

    return re.sub(r'([^{}]+)\{([^{}]*)\}', update_rule, base_qss)


def theme_override(profile: str) -> str:
    """Themed content surfaces; the persistent dark sidebar remains legible."""
    if profile == 'standard':
        return ''
    p = PALETTES.get(profile, PALETTES['standard'])
    return f'''
    QWidget#appRoot, QWidget#scrollContent {{ background: {p.background}; color: {p.foreground}; }}
    QFrame#topBar, QFrame#footerBar {{ background: {p.panel}; border-color: {p.border}; }}
    QFrame#card, QFrame#optionCard {{ background: {p.panel}; border-color: {p.border}; }}
    QFrame#innerCard {{ background: {p.surface}; border-color: {p.border}; }}
    QLabel#pageTitle, QLabel#sectionTitle, QLabel#cardTitle, QLabel#number,
    QLabel#bodyText, QLabel#topBarTitle {{ color: {p.foreground}; }}
    QLabel#pageDescription, QLabel#eyebrow, QLabel#subtle, QLabel#micro,
    QLabel#footerText {{ color: {p.muted}; }}
    QLabel#pill {{ background: {p.surface}; color: {p.foreground}; }}
    QPushButton#secondaryButton, QPushButton#presetButton {{
        background: {p.panel}; color: {p.foreground}; border-color: {p.border};
    }}
    QPushButton#presetButton:checked {{ background: {p.surface}; border-color: {p.accent}; color: {p.foreground}; }}
    QPushButton#primaryButton {{ background: {p.accent}; color: {p.accent_text}; border-color: {p.accent}; }}
    QLineEdit, QTextEdit, QComboBox {{ background: {p.panel}; color: {p.foreground}; border-color: {p.border}; }}
    QComboBox QAbstractItemView {{ background: {p.panel}; color: {p.foreground}; }}
    QFrame#sidebar QLabel#brandName {{ color: #FFFFFF; }}
    QFrame#sidebar QLabel#brandSub {{ color: #98A4C8; }}
    QFrame#sidebar QLabel#sideSection {{ color: #8591B6; }}
    QFrame#sidebar QLabel#sidebarFoot {{ color: #8390B1; }}
    QFrame#sidebar QFrame#innerCard {{ background: #252B49; border-color: #3B4267; }}
    QFrame#sidebar QFrame#innerCard QLabel#micro {{ color: #BCC7E4; }}
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
        self.body = QLabel('Make text easier to read with size, spacing and contrast adjustments.\n'
                           'This live preview updates as you move the controls.')
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
        self.setStyleSheet(f'QFrame#smartPreview {{ background-color: {p.background}; '
                           f'border: 1px solid {p.border}; border-radius: 15px; }}')
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
        self.action.setStyleSheet(f'QPushButton {{ background: {p.accent}; color: {p.accent_text}; '
                                  'padding: 10px 16px; border: none; border-radius: 9px; font-weight: 700; }')
        action_font = QFont(self.action.font())
        action_font.setPixelSize(_font_size(font_size_pct, 12))
        self.action.setFont(action_font)
