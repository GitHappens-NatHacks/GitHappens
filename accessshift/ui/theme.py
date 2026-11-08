"""AccessShift visual system: brand palette, colour themes and app-wide reading settings.

Everything here is presentation only. The four colour themes a person can pick
(Standard, High contrast, Warm reading, Cool blue) are expressed as one token set,
so every AccessShift window (control center, Demo Lab, hands-free view) looks the
same and follows the same text size and letter spacing.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from string import Template

from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication

from accessshift.modules.smartinterface.visual_controller import Palette

# Brand palette (the agreed AccessShift colours).
DEEP_TEAL = '#176F6C'        # primary buttons, branding
SOFT_MINT = '#E5F2EF'        # cards, highlights
WARM_CREAM = '#FAF2DE'       # background sections
FOREST_GREEN = '#1C302C'     # sidebar, headings
ACCESSIBLE_BLUE = '#3478D4'  # links, active controls
PURE_WHITE = '#FFFFFF'       # main background
CHARCOAL = '#252B29'         # main text
MUTED_GREY_GREEN = '#65716D'  # secondary text


@dataclass(frozen=True)
class Theme:
    bg: str            # main background
    section: str       # background sections
    card: str          # card surface
    mint: str          # highlight surface
    sidebar: str
    sidebar_text: str
    sidebar_muted: str
    sidebar_active: str
    heading: str
    text: str
    muted: str
    primary: str
    primary_hover: str
    on_primary: str
    active: str        # links, focus, selected controls
    border: str
    highlight: str     # word highlighting marker


THEMES: dict[str, Theme] = {
    'standard': Theme(
        bg=PURE_WHITE, section=WARM_CREAM, card=PURE_WHITE, mint=SOFT_MINT,
        sidebar=FOREST_GREEN, sidebar_text='#E1EEEA', sidebar_muted='#97B5AC', sidebar_active='#2A4A43',
        heading=FOREST_GREEN, text=CHARCOAL, muted=MUTED_GREY_GREEN,
        primary=DEEP_TEAL, primary_hover='#115654', on_primary=PURE_WHITE,
        active=ACCESSIBLE_BLUE, border='#D5E2DE', highlight='#FFE07A',
    ),
    'high_contrast': Theme(
        bg='#0B0F0E', section='#121A18', card='#121A18', mint='#1E2B28',
        sidebar='#000000', sidebar_text='#FFFFFF', sidebar_muted='#D2E2DC', sidebar_active='#1E2B28',
        heading='#FFFFFF', text='#FFFFFF', muted='#DCE6E2',
        primary='#FFD84D', primary_hover='#FFE47F', on_primary='#101010',
        active='#8EC5FF', border='#CFE0DA', highlight='#FFD84D',
    ),
    'warm': Theme(
        bg='#FFFBF2', section=WARM_CREAM, card=PURE_WHITE, mint='#F3E8CF',
        sidebar='#2B2418', sidebar_text='#F5EBD8', sidebar_muted='#C9B48F', sidebar_active='#3E3423',
        heading='#2B2418', text='#332718', muted='#6B563B',
        primary=DEEP_TEAL, primary_hover='#115654', on_primary=PURE_WHITE,
        active='#2F6DC0', border='#E5D5B4', highlight='#FFD978',
    ),
    'cool': Theme(
        bg='#F4F8FD', section='#E6F0FA', card=PURE_WHITE, mint='#DCEAF8',
        sidebar='#132C44', sidebar_text='#DCEBFA', sidebar_muted='#8FAFCC', sidebar_active='#1F3F5E',
        heading='#132C44', text='#152C45', muted='#486784',
        primary='#255FD3', primary_hover='#1C4CAD', on_primary=PURE_WHITE,
        active='#255FD3', border='#C5DAEE', highlight='#FFE58A',
    ),
}

THEME_LABELS = (
    ('standard', 'Standard'),
    ('high_contrast', 'High contrast'),
    ('warm', 'Warm reading'),
    ('cool', 'Cool blue'),
)


def theme(profile: str) -> Theme:
    return THEMES.get(profile, THEMES['standard'])


def gaze_palette(profile: str) -> Palette:
    """The same theme in the palette shape the hands-free (gaze) screens use."""
    t = theme(profile)
    return Palette(
        background=t.section, panel=t.card, surface=t.mint, foreground=t.text,
        muted=t.muted, border=t.border, accent=t.primary, accent_text=t.on_primary,
    )


# Labels whose size must stay fixed so navigation never overflows at large text sizes.
FIXED_SIZE_SELECTORS = ('#navButton', '#sideSection', '#brandName', '#brandSub', '#sidebarFoot',
                        '#topBarTitle', '#footerText', '#railButton', '#railTitle')

_QSS_TEMPLATE = Template(Path(__file__).with_name('control_center_styles.qss').read_text(encoding='utf-8'))


def scale_font_sizes(qss: str, font_size_pct: int, fixed: tuple[str, ...] = FIXED_SIZE_SELECTORS) -> str:
    pct = max(90, min(160, int(font_size_pct)))

    def update_rule(match: re.Match[str]) -> str:
        selector, body = match.group(1), match.group(2)
        if any(name in selector for name in fixed):
            return match.group(0)
        body = re.sub(r'font-size\s*:\s*(\d+)px',
                      lambda m: f'font-size: {max(10, round(int(m.group(1)) * pct / 100))}px', body)
        return selector + '{' + body + '}'

    return re.sub(r'([^{}]+)\{([^{}]*)\}', update_rule, qss)


def stylesheet(font_size_pct: int = 100, color_profile: str = 'standard') -> str:
    """The complete AccessShift stylesheet for a text size and colour theme."""
    tokens = {k: v for k, v in theme(color_profile).__dict__.items()}
    return scale_font_sizes(_QSS_TEMPLATE.substitute(tokens), font_size_pct)


def apply_letter_spacing(px: int) -> None:
    """Letter spacing for every AccessShift window, not only one page.

    The application font carries the spacing; re-applying each window's stylesheet
    makes Qt re-resolve fonts that a stylesheet sized, so the spacing reaches them too.
    """
    app = QApplication.instance()
    if app is None:
        return
    px = max(0, min(4, int(px)))
    font = QFont(app.font())
    if abs(font.letterSpacing() - px) < 0.01 and font.letterSpacingType() == QFont.SpacingType.AbsoluteSpacing:
        return
    font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, px)
    app.setFont(font)
    for window in app.topLevelWidgets():
        window.setStyleSheet(window.styleSheet())
