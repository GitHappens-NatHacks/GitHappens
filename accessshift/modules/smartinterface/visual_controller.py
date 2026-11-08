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
    'standard': Palette('#F7F7F5', '#FFFFFF', '#F3F1FF', '#1B1B28', '#70707D', '#E9E8ED', '#6B57E8', '#FFFFFF'),
    'high_contrast': Palette('#080A14', '#121628', '#1E2440', '#FFFFFF', '#E7ECFC', '#BECBF2', '#F7DC5E', '#101010'),
    'warm': Palette('#FCF5E9', '#FFFCF7', '#FFF0DB', '#3D3027', '#675447', '#E5D4C2', '#7255D3', '#FFFFFF'),
    'cool': Palette('#EDF5FC', '#FFFFFF', '#E2F0FC', '#182D41', '#49627D', '#BFD6E9', '#3D67C9', '#FFFFFF'),
}


def _font_size(percentage: int, base: int) -> int:
    return max(10, round(base * max(90, min(160, int(percentage))) / 100))


def scaled_stylesheet(base_qss: str, font_size_pct: int) -> str:
    """Scale content typography without making navigation/sidebar overflow."""
    pct = max(90, min(160, int(font_size_pct)))
    fixed = ('#navButton', '#brandName', '#sidebarIntro', '#sideCaption',
             '#sideFoot', '#sidebarFoot', '#sidebarEyebrow', '#logoMark', '#topTitle', '#topBadge',
             '#brandName', '#brandSub', '#navTab', '#statusTag', '#footerText')

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
    """Theme AccessShift-owned surfaces, not external applications or screens.

    The Focus 2.0 top navigation + tool list must all receive palette colours,
    including labels in every card.  These selectors also retain legacy names
    for older local UI components.
    """
    if profile == 'standard':
        return ''
    p = PALETTES.get(profile, PALETTES['standard'])
    return f'''
    QWidget#appRoot, QWidget#scrollContent, QWidget#contentBody,
    QStackedWidget#pageStack {{ background: {p.background}; color: {p.foreground}; }}
    QFrame#topbar, QFrame#appFooter, QFrame#topBar,
    QFrame#footerBar {{ background: {p.panel}; border-color: {p.border}; }}
    QFrame#surface, QFrame#presetBar, QFrame#toolList,
    QFrame#card, QFrame#toolCard, QFrame#optionCard {{
        background: {p.panel}; border-color: {p.border};
    }}
    QFrame#tabsBar, QFrame#inlineToggle, QFrame#innerCard {{
        background: {p.surface}; border-color: {p.border};
    }}
    QFrame#lineDivider {{ background: {p.border}; }}
    QLabel {{ color: {p.foreground}; }}
    QLabel#pageTitle, QLabel#sectionTitle, QLabel#cardTitle,
    QLabel#fieldLabel, QLabel#brandName, QLabel#toolTitle {{ color: {p.foreground}; }}
    QLabel#pageDescription, QLabel#body, QLabel#toolDetail,
    QLabel#supportText, QLabel#footerText, QLabel#brandSub,
    QLabel#sectionHint, QLabel#disclaimer {{ color: {p.muted}; }}
    QLabel#eyebrow {{ color: {p.accent}; }}
    QLabel#toolNumber, QLabel#valuePill {{
        background: {p.surface}; color: {p.foreground}; border-color: {p.border};
    }}
    QLabel#statusTag {{ background: {p.surface}; color: {p.foreground}; }}
    QPushButton#navTab, QPushButton#detailTab, QPushButton#navButton {{
        background: transparent; color: {p.foreground};
    }}
    QPushButton#navTab:checked, QPushButton#detailTab:checked,
    QPushButton#navButton:checked {{
        background: {p.surface}; border: 1px solid {p.accent}; color: {p.foreground};
    }}
    QPushButton#primaryButton {{
        background: {p.accent}; color: {p.accent_text}; border-color: {p.accent};
    }}
    QPushButton#secondaryButton {{
        background: {p.panel}; color: {p.foreground}; border-color: {p.border};
    }}
    QLineEdit, QTextEdit, QComboBox {{
        background: {p.panel}; color: {p.foreground}; border-color: {p.border};
    }}
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
