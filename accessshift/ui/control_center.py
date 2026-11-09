"""AccessShift control center: preferences-first desktop UI for macOS and Windows.

Pages: an introductory Home page and guided introduction, the Dashboard, the
accessibility profile (top-right corner), and one tab per feature (Head movement,
which also covers eye and blink control, SteadyHand, SmartInterface), each with its own demo.
It uses the existing AdaptiveEngine and SteadyHandController APIs unchanged.
"""
from __future__ import annotations

import math
from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QKeySequence, QPainter, QPen, QShortcut
from PySide6.QtWidgets import (
    QApplication, QButtonGroup, QFrame, QGridLayout, QHBoxLayout, QMainWindow,
    QMessageBox, QPushButton, QScrollArea, QSizePolicy, QSlider, QStackedWidget,
    QVBoxLayout, QWidget,
)

from accessshift.engine.adaptive_engine import AdaptiveEngine
from accessshift.modules.smartinterface import ScreenTintManager
from accessshift.modules.smartinterface.screen_overlay import TINT_COLORS
from accessshift.modules.steadyhand.controller import SteadyHandController
from accessshift.ui import icons
from accessshift.ui import theme as theme_mod
from accessshift.ui.control_center_components import (
    ChoiceCard, PreferenceRow, Switch, SwatchButton, button, card, divider, label,
)
from accessshift.ui.control_center_settings import (
    PROFILES, load_settings, save_settings,
)
from accessshift.ui.steadyhand_panel import LABELS, SEQUENCE, SteadyHandTrialPanel, TremorPlayground  # noqa: F401
from accessshift.ui.word_highlight import WordHighlighter

MODULE_KEYS = ('gaze_control', 'steady_hand', 'smart_interface', 'predictive_speech')

# The four AccessShift features, in the order they appear everywhere.
FEATURES = (
    ('gaze', 'head', 'Head movement', 'Point with your head or your eyes, and blink to select. Only a webcam is needed.'),
    ('steady', 'steady', 'SteadyHand',
     'Steady the pointer through Parkinsonian tremor and keep a simple motor session for clinic review.'),
    ('interface', 'interface', 'SmartInterface', 'Bigger text, calmer colours and simpler, step-by-step screens.'),
)

PAGE_TITLES = {
    'overview': 'Dashboard', 'personalize': 'My accessibility profile', 'gaze': 'Head movement',
    'steady': 'SteadyHand', 'interface': 'SmartInterface',
}

PROFILE_CHIPS = {
    'als': ('Head or eyes', 'Blink to select', 'SmartInterface'),
    'parkinsons': ('SteadyHand', 'SmartInterface'),
    'cognitive': ('SmartInterface', 'Simplified layout'),
    'custom': ('Any combination',),
}
PROFILE_ICONS = {'als': 'head', 'parkinsons': 'steady', 'cognitive': 'interface', 'custom': 'profile'}

INTRO_SLIDES = (
    ('profile', 'Welcome to AccessShift',
     'AccessShift changes how your computer responds to you, so everyday tasks like booking a doctor\'s '
     'appointment take less effort. Here is what it can do.',
     ('Works with the webcam you already have', 'Every setting can be changed at any time',
      'Try each feature safely on a sample healthcare form')),
    ('head', 'Head movement',
     'Point by turning your head, or with your eyes. Hold still for a moment, or blink slowly, to choose.',
     ('Large options in a calm, full-screen view', 'Head or eyes: pick whichever feels easier',
      'Quit at any time with the Quit hands-free button')),
    ('steady', 'SteadyHand',
     'SteadyHand softens tremor on the pointer, widens hard-to-hit targets, and keeps a motor session you can export.',
     ('Quieter aiming with tremor', 'Clearer booking-step trials', 'A session chart clinicians can review')),
    ('interface', 'SmartInterface',
     'Reshapes busy screens: larger text, extra letter spacing, calmer colours and one step at a time.',
     ('Text size and spacing across the whole app', 'Word highlighting to help you keep your place',
      'Colour themes and a gentle screen tint')),
    ('check', 'Make it yours',
     'Pick a starting profile and fine-tune it, or go straight to your dashboard. You can come back to this '
     'introduction from the Home page whenever you like.',
     ()),
)


class HeroArt(QWidget):
    """The Home page illustration: four tools orbiting the person they adapt to."""

    ORBIT = (('head', 'Head', -140), ('eye', 'Eyes', -40), ('steady', 'Steady', 40), ('interface', 'Clear', 140))

    def __init__(self):
        super().__init__()
        self.setMinimumSize(360, 360)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setAccessibleName('Illustration: head, eyes, steady hand and clear screens around a person')
        self.theme = theme_mod.theme('standard')

    def set_theme(self, t: theme_mod.Theme) -> None:
        self.theme = t
        self.update()

    def paintEvent(self, event) -> None:
        t = self.theme
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        side = min(self.width(), self.height())
        c = QPointF(self.width() / 2, self.height() / 2)
        # soft rings
        for i, r in enumerate((0.49, 0.40, 0.31)):
            ring = QColor(t.mint)
            ring.setAlphaF(0.55 + 0.15 * i)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(ring)
            p.drawEllipse(c, side * r, side * r)
        # dashed orbit
        orbit_r = side * 0.36
        pen = QPen(QColor(t.primary), 1.4, Qt.PenStyle.DashLine)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(c, orbit_r, orbit_r)
        # centre: the person
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(t.primary))
        p.drawEllipse(c, side * 0.15, side * 0.15)
        size = round(side * 0.16)
        p.drawPixmap(round(c.x() - size / 2), round(c.y() - size / 2), icons.pixmap('profile', t.on_primary, size))
        # satellites
        disc = side * 0.085
        font = p.font()
        font.setPixelSize(max(12, round(side * 0.034)))
        font.setBold(True)
        p.setFont(font)
        for name, caption, angle in self.ORBIT:
            a = math.radians(angle)
            pt = QPointF(c.x() + orbit_r * math.sin(a), c.y() - orbit_r * math.cos(a))
            shadow = QColor(t.heading)
            shadow.setAlphaF(0.10)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(shadow)
            p.drawEllipse(QPointF(pt.x(), pt.y() + 4), disc, disc)
            p.setPen(QPen(QColor(t.border), 1))
            p.setBrush(QColor(t.card))
            p.drawEllipse(pt, disc, disc)
            isz = round(disc * 1.05)
            p.drawPixmap(round(pt.x() - isz / 2), round(pt.y() - isz / 2), icons.pixmap(name, t.primary, isz))
            p.setPen(QColor(t.heading))
            p.drawText(QRectF(pt.x() - 60, pt.y() + disc + 4, 120, 24), Qt.AlignmentFlag.AlignCenter, caption)
        p.end()


class SlideArt(QWidget):
    """Introduction illustration: one feature icon inside soft rings."""

    def __init__(self):
        super().__init__()
        self.setMinimumSize(280, 280)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.theme = theme_mod.theme('standard')
        self.name = 'profile'

    def set_icon(self, name: str) -> None:
        self.name = name
        self.update()

    def set_theme(self, t: theme_mod.Theme) -> None:
        self.theme = t
        self.update()

    def paintEvent(self, event) -> None:
        t = self.theme
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        side = min(self.width(), self.height())
        c = QPointF(self.width() / 2, self.height() / 2)
        for i, r in enumerate((0.48, 0.38)):
            ring = QColor(t.mint)
            ring.setAlphaF(0.6 + 0.2 * i)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(ring)
            p.drawEllipse(c, side * r, side * r)
        p.setBrush(QColor(t.primary))
        p.drawEllipse(c, side * 0.26, side * 0.26)
        size = round(side * 0.26)
        p.drawPixmap(round(c.x() - size / 2), round(c.y() - size / 2), icons.pixmap(self.name, t.on_primary, size))
        p.end()


class HeadStartButton(QPushButton):
    """Big Start/Stop button for hands-free control (keeps the toggle's set_value API)."""

    def __init__(self, start_text: str = 'Start head control', stop_text: str = 'Stop head control'):
        super().__init__()
        self._texts = (start_text, stop_text)
        self.setMinimumHeight(64)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet('QPushButton { font-size: 18px; }')  # colours still come from the app theme
        self.set_value(False)

    def set_texts(self, start_text: str, stop_text: str) -> None:
        self._texts = (start_text, stop_text)

    def set_value(self, on: bool) -> None:
        self.setText(self._texts[1] if on else self._texts[0])
        self.setObjectName('secondaryButton' if on else 'primaryButton')
        self.style().unpolish(self)
        self.style().polish(self)


class FeatureCard(QFrame):
    """Dashboard entry for one feature: what it does, its live status and two direct actions."""

    def __init__(self, key: str, icon_name: str, title: str, description: str):
        super().__init__()
        self.setObjectName('card')
        self.key = key
        lay = QVBoxLayout(self)
        lay.setContentsMargins(22, 20, 22, 18)
        lay.setSpacing(10)
        top = QHBoxLayout()
        top.setSpacing(14)
        self.tile = icons.IconTile(icon_name, 48)
        top.addWidget(self.tile, 0, Qt.AlignmentFlag.AlignVCenter)
        top.addWidget(label(title, 'featureTitle', True), 1, Qt.AlignmentFlag.AlignVCenter)
        self.status = label('Off', 'pill')
        top.addWidget(self.status, 0, Qt.AlignmentFlag.AlignVCenter)
        lay.addLayout(top)
        lay.addWidget(label(description, 'featureDesc', True))
        self.meta = label('', 'featureMeta', True)
        lay.addWidget(self.meta)
        lay.addStretch(1)
        actions = QHBoxLayout()
        actions.setSpacing(8)
        self.open_button = button('Open', 'secondaryButton')
        self.open_button.setAccessibleName(f'Open {title}')
        self.demo_button = button('Try the demo', 'linkButton')
        self.demo_button.setAccessibleName(f'Try the {title} demo')
        actions.addWidget(self.open_button)
        actions.addWidget(self.demo_button)
        actions.addStretch(1)
        lay.addLayout(actions)

    def set_status(self, text: str, good: bool) -> None:
        self.status.setText(text)
        self.status.setObjectName('goodPill' if good else 'pill')
        self.status.style().unpolish(self.status)
        self.status.style().polish(self.status)


class MainWindow(QMainWindow):
    """Drop-in replacement for accessshift.ui.main_window.MainWindow(repo_root)."""

    preferences_changed = Signal(object)  # dict; app services may subscribe
    calibration_requested = Signal()  # gaze team can connect worker/controller
    assistance_changed = Signal(bool)

    # Hands-free selection speed: Relaxed 1.6 s, Normal 1.1 s, Quick 0.8 s.
    HEAD_SPEEDS = (('relaxed', 'Relaxed', 1600), ('normal', 'Normal', 1100), ('quick', 'Quick', 800))

    def __init__(self, repo_root: Path):
        super().__init__()
        self.repo_root = Path(repo_root)
        self.prefs = load_settings()
        self.engine = AdaptiveEngine(self)
        self.steady = SteadyHandController()
        self.speech = None
        self._nav = {}
        self._pages = {}
        self._bound_rows: list[tuple[str, str, PreferenceRow]] = []  # (kind, key, row)
        self._sliders = {}
        self._preset_buttons = {}
        self._icon_tiles: list[icons.IconTile] = []
        self._brand_tiles: list[icons.IconTile] = []
        self._themed_art: list = []
        self._nav_icons: list[tuple[QPushButton, str]] = []
        self.tint_manager = ScreenTintManager(QApplication.instance())
        self.highlighter = WordHighlighter(self)
        self._syncing_engine = True
        self._build_ui()
        self.tint_manager.register_window(self)  # Restrict tint to this application window
        self.engine.modules_changed.connect(self._on_external_modules_changed)
        self._apply_preferences_to_engine()
        self._syncing_engine = False
        self._refresh()
        self._navigate('home')
        self.resize(1240, 820)
        self.setMinimumSize(960, 660)
        self.setWindowTitle('AccessShift AI')

    # ------------------------------------------------------------------ shell
    def _build_ui(self):
        root = QWidget()
        root.setObjectName('appRoot')
        self.setCentralWidget(root)
        outer = QHBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        side = QFrame()
        side.setObjectName('sidebar')
        side.setFixedWidth(250)
        self.sidebar = side
        side_l = QVBoxLayout(side)
        side_l.setContentsMargins(16, 26, 16, 20)
        side_l.setSpacing(4)
        brand = QHBoxLayout()
        brand.setSpacing(12)
        self.brand_mark = icons.IconTile('profile', 40)
        brand.addWidget(self.brand_mark)
        text_l = QVBoxLayout()
        text_l.setSpacing(0)
        text_l.addWidget(label('AccessShift', 'brandName'))
        text_l.addWidget(label('Accessibility, your way', 'brandSub', True))
        brand.addLayout(text_l, 1)
        side_l.addLayout(brand)
        side_l.addSpacing(26)
        nav_sections = [
            (None, [('home', 'home', 'Home'), ('overview', 'dashboard', 'Dashboard')]),
            ('Features', [(key, icon_name, title) for key, icon_name, title, _ in FEATURES]),
        ]
        for section, entries in nav_sections:
            if section:
                side_l.addSpacing(14)
                side_l.addWidget(label(section, 'sideSection'))
                side_l.addSpacing(4)
            for key, icon_name, text in entries:
                nav_button = button(text, 'navButton')
                nav_button.setCheckable(True)
                nav_button.setMinimumHeight(42)
                nav_button.clicked.connect(lambda _=False, k=key: self._navigate(k))
                nav_button.setAccessibleName(text)
                self._nav_icons.append((nav_button, icon_name))
                side_l.addWidget(nav_button)
                self._nav[key] = nav_button
        side_l.addStretch()
        side_l.addWidget(label('GitHappens  ·  natHacks 2026', 'sidebarFoot'))
        outer.addWidget(side)

        right = QWidget()
        self.workspace = right
        right_l = QVBoxLayout(right)
        right_l.setContentsMargins(0, 0, 0, 0)
        right_l.setSpacing(0)
        top_bar = QFrame()
        top_bar.setObjectName('topBar')
        self.top_bar = top_bar
        top_l = QHBoxLayout(top_bar)
        top_l.setContentsMargins(32, 12, 24, 12)
        top_l.setSpacing(10)
        self.top_title = label('Dashboard', 'topBarTitle')
        top_l.addWidget(self.top_title)
        top_l.addStretch()
        self._demo_shortcut = button('Open Demo Lab', 'secondaryButton')
        self._demo_shortcut.setToolTip('Show all four AccessShift features in one demo window')
        self._demo_shortcut.setMinimumHeight(38)
        self._demo_shortcut.clicked.connect(lambda: self._open_demo_lab('start'))
        top_l.addWidget(self._demo_shortcut)
        self.profile_button = self._make_profile_button()
        top_l.addWidget(self.profile_button)
        self.top_bar_layout = top_l
        right_l.addWidget(top_bar)

        self.stack = QStackedWidget()
        right_l.addWidget(self.stack, 1)
        for key, method in [
            ('home', self._page_home),
            ('intro', self._page_intro),
            ('overview', self._page_overview),
            ('personalize', self._page_personalize),
            ('gaze', self._page_gaze),
            ('steady', self._page_steady),
            ('interface', self._page_interface),
        ]:
            page = method()
            self._pages[key] = page
            self.stack.addWidget(page)
        foot = QFrame()
        foot.setObjectName('footerBar')
        self.footer = foot
        fl = QHBoxLayout(foot)
        fl.setContentsMargins(32, 9, 32, 9)
        fl.addWidget(label('AccessShift AI', 'footerText'))
        fl.addStretch()
        self.footer_status = label('Settings saved on this device', 'footerText')
        fl.addWidget(self.footer_status)
        right_l.addWidget(foot)
        outer.addWidget(right, 1)

    def _make_profile_button(self) -> QPushButton:
        b = button('My accessibility profile', 'profileButton')
        b.setCheckable(True)
        b.setMinimumHeight(38)
        b.setAccessibleName('My accessibility profile')
        b.clicked.connect(lambda: self._navigate('personalize'))
        self._nav_icons.append((b, 'profile'))
        return b

    def _tile(self, name: str, size: int = 44) -> icons.IconTile:
        tile = icons.IconTile(name, size)
        self._icon_tiles.append(tile)
        return tile

    def _page(self, title, subtitle, *, icon_name: str | None = None):
        scroller = QScrollArea()
        scroller.setWidgetResizable(True)
        scroller.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        container = QWidget()
        container.setObjectName('scrollContent')
        content = QVBoxLayout(container)
        content.setContentsMargins(40, 32, 40, 40)
        content.setSpacing(18)
        head = QHBoxLayout()
        head.setSpacing(16)
        if icon_name:
            head.addWidget(self._tile(icon_name, 56), 0, Qt.AlignmentFlag.AlignTop)
        texts = QVBoxLayout()
        texts.setSpacing(6)
        texts.addWidget(label(title, 'pageTitle', True))
        texts.addWidget(label(subtitle, 'pageDescription', True))
        head.addLayout(texts, 1)
        content.addLayout(head)
        content.addSpacing(6)
        scroller.setWidget(container)
        return scroller, content

    def _section(self, lay, title, subtitle=None):
        lay.addSpacing(8)
        lay.addWidget(label(title, 'sectionTitle'))
        if subtitle:
            lay.addWidget(label(subtitle, 'bodyText', True))

    def _bind_row(self, kind: str, key: str, heading: str, details: str, *, framed: bool = True) -> PreferenceRow:
        """A toggle row bound to a module ('module') or a boolean option ('option')."""
        row = PreferenceRow(heading, details, framed=framed)
        if kind == 'module':
            row.changed.connect(lambda value, k=key: self._change_module(k, value))
        elif kind == 'option':
            row.changed.connect(lambda value, k=key: self._change_option(k, bool(value)))
        else:  # 'tint'
            row.changed.connect(self._set_screen_tint)
        self._bound_rows.append((kind, key, row))
        return row

    # ------------------------------------------------------------------ Home
    def _page_home(self):
        page = QWidget()
        page.setObjectName('homeRoot')
        lay = QVBoxLayout(page)
        lay.setContentsMargins(48, 28, 40, 36)
        lay.setSpacing(0)
        top = QHBoxLayout()
        self.home_mark = icons.IconTile('profile', 40)
        self._brand_tiles.append(self.home_mark)
        top.addWidget(self.home_mark)
        top.addSpacing(10)
        top.addWidget(label('AccessShift', 'homeBrand'))
        top.addStretch(1)
        self.home_profile_button = button('My accessibility profile', 'profileButton')
        self.home_profile_button.setMinimumHeight(40)
        self.home_profile_button.clicked.connect(lambda: self._navigate('personalize'))
        self._nav_icons.append((self.home_profile_button, 'profile'))
        top.addWidget(self.home_profile_button)
        lay.addLayout(top)
        lay.addStretch(2)

        body = QHBoxLayout()
        body.setSpacing(36)
        left = QVBoxLayout()
        left.setSpacing(22)
        title = label('Your computer,\nshaped around you.', 'homeTitle', True)
        left.addWidget(title)
        left.addWidget(label(
            'AccessShift lets you point with your head or eyes, steadies a shaky hand, and turns busy screens '
            'into calm, clear steps, so tasks like booking a healthcare appointment feel easy again.',
            'homeLead', True))
        ctas = QHBoxLayout()
        ctas.setSpacing(18)
        explore = button('Explore AccessShift', 'ctaButton')
        explore.setMinimumHeight(60)
        explore.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self._explore_button = explore
        explore.clicked.connect(lambda: self._start_intro(0))
        ctas.addWidget(explore)
        skip = button('Go to my dashboard', 'linkButton')
        skip.clicked.connect(lambda: self._navigate('overview'))
        ctas.addWidget(skip)
        ctas.addStretch(1)
        left.addLayout(ctas)
        left.addSpacing(10)
        left.addWidget(label('Jump to a feature', 'homeNote'))
        chips = QGridLayout()
        chips.setHorizontalSpacing(8)
        chips.setVerticalSpacing(8)
        self._home_feature_links = []
        for i, (key, icon_name, title_text, _desc) in enumerate(FEATURES):
            b = button(title_text, 'featureLink')
            b.setMinimumHeight(40)
            b.clicked.connect(lambda _=False, n=i + 1: self._start_intro(n))
            self._home_feature_links.append((b, icon_name))
            chips.addWidget(b, 0, i)
        left.addLayout(chips)
        body.addLayout(left, 11)
        self.hero_art = HeroArt()
        self._themed_art.append(self.hero_art)
        body.addWidget(self.hero_art, 9)
        lay.addLayout(body)
        lay.addStretch(3)
        return page

    # ------------------------------------------------------------------ Introduction
    def _page_intro(self):
        page = QWidget()
        page.setObjectName('homeRoot')
        lay = QVBoxLayout(page)
        lay.setContentsMargins(48, 28, 40, 36)
        lay.setSpacing(0)
        top = QHBoxLayout()
        intro_mark = icons.IconTile('profile', 40)
        self._brand_tiles.append(intro_mark)
        top.addWidget(intro_mark)
        top.addSpacing(10)
        top.addWidget(label('AccessShift', 'homeBrand'))
        top.addStretch(1)
        skip = button('Skip introduction', 'linkButton')
        skip.clicked.connect(lambda: self._navigate('overview'))
        top.addWidget(skip)
        lay.addLayout(top)
        lay.addStretch(1)

        body = QHBoxLayout()
        body.setSpacing(48)
        self.slide_art = SlideArt()
        self._themed_art.append(self.slide_art)
        body.addWidget(self.slide_art, 8)
        text = QVBoxLayout()
        text.setSpacing(16)
        self.intro_step = label('', 'introStep')
        self.intro_title = label('', 'introTitle', True)
        self.intro_lead = label('', 'introLead', True)
        text.addWidget(self.intro_step)
        text.addWidget(self.intro_title)
        text.addWidget(self.intro_lead)
        self.intro_points = []
        for _ in range(3):
            row = QHBoxLayout()
            row.setSpacing(12)
            tick = self._tile('check', 26)
            point = label('', 'introPoint', True)
            row.addWidget(tick, 0, Qt.AlignmentFlag.AlignTop)
            row.addWidget(point, 1)
            text.addLayout(row)
            self.intro_points.append((tick, point))
        self.intro_actions = QWidget()
        actions = QHBoxLayout(self.intro_actions)
        actions.setContentsMargins(0, 8, 0, 0)
        actions.setSpacing(12)
        setup = button('Set up my profile', 'ctaButton')
        setup.clicked.connect(lambda: self._navigate('personalize'))
        dash = button('Go to my dashboard', 'secondaryButton')
        dash.setMinimumHeight(56)
        dash.clicked.connect(lambda: self._navigate('overview'))
        actions.addWidget(setup)
        actions.addWidget(dash)
        actions.addStretch(1)
        text.addWidget(self.intro_actions)
        self.intro_open = button('', 'secondaryButton')
        self.intro_open.clicked.connect(self._open_intro_feature)
        text.addWidget(self.intro_open, 0, Qt.AlignmentFlag.AlignLeft)
        body.addLayout(text, 11)
        lay.addLayout(body)
        lay.addStretch(1)

        nav = QHBoxLayout()
        nav.setSpacing(10)
        self.intro_back = button('Back', 'secondaryButton')
        self.intro_back.setMinimumWidth(120)
        self.intro_back.clicked.connect(lambda: self._show_slide(self._slide - 1))
        nav.addWidget(self.intro_back)
        nav.addStretch(1)
        self.intro_dots = []
        dots = QButtonGroup(page)
        for i in range(len(INTRO_SLIDES)):
            dot = QPushButton()
            dot.setObjectName('dotButton')
            dot.setCheckable(True)
            dot.setCursor(Qt.CursorShape.PointingHandCursor)
            dot.setAccessibleName(f'Introduction step {i + 1}: {INTRO_SLIDES[i][1]}')
            dot.clicked.connect(lambda _=False, n=i: self._show_slide(n))
            dots.addButton(dot)
            nav.addWidget(dot)
            self.intro_dots.append(dot)
        nav.addStretch(1)
        self.intro_next = button('Next', 'primaryButton')
        self.intro_next.setMinimumWidth(120)
        self.intro_next.clicked.connect(lambda: self._show_slide(self._slide + 1))
        nav.addWidget(self.intro_next)
        lay.addLayout(nav)
        for key, step in ((Qt.Key.Key_Right, 1), (Qt.Key.Key_Left, -1)):
            shortcut = QShortcut(QKeySequence(key), page)
            shortcut.activated.connect(lambda s=step: self._show_slide(self._slide + s))
        self._slide = 0
        self._show_slide(0)
        return page

    def _start_intro(self, slide: int = 0) -> None:
        self._show_slide(slide)
        self._navigate('intro')

    def _show_slide(self, index: int) -> None:
        index = max(0, min(len(INTRO_SLIDES) - 1, index))
        self._slide = index
        icon_name, title, lead, points = INTRO_SLIDES[index]
        last = index == len(INTRO_SLIDES) - 1
        self.slide_art.set_icon(icon_name)
        self.intro_step.setText(f'Step {index + 1} of {len(INTRO_SLIDES)}')
        self.intro_title.setText(title)
        self.intro_lead.setText(lead)
        for (tick, point), text in zip(self.intro_points, list(points) + [''] * 3):
            tick.setVisible(bool(text))
            point.setVisible(bool(text))
            point.setText(text)
        self.intro_actions.setVisible(last)
        feature = FEATURES[index - 1] if 1 <= index <= len(FEATURES) else None
        self.intro_open.setVisible(feature is not None)
        if feature is not None:
            self.intro_open.setText(f'Open {feature[2]}')
        self.intro_back.setEnabled(index > 0)
        self.intro_next.setVisible(not last)
        for i, dot in enumerate(self.intro_dots):
            dot.setChecked(i == index)

    def _open_intro_feature(self) -> None:
        if 1 <= self._slide <= len(FEATURES):
            self._navigate(FEATURES[self._slide - 1][0])

    # ------------------------------------------------------------------ Dashboard
    def _page_overview(self):
        page, lay = self._page('Dashboard', 'Your tools at a glance. Open one to adjust it, or try its demo.')
        band, bl = card(name='band', margins=26, spacing=8)
        row = QHBoxLayout()
        row.setSpacing(20)
        texts = QVBoxLayout()
        texts.setSpacing(6)
        self.overview_profile = label('Your profile: Personalize everything', 'bandTitle', True)
        self.overview_summary = label('', 'bandText', True)
        texts.addWidget(self.overview_profile)
        texts.addWidget(self.overview_summary)
        row.addLayout(texts, 1)
        edit = button('Edit my profile', 'primaryButton')
        edit.clicked.connect(lambda: self._navigate('personalize'))
        row.addWidget(edit, 0, Qt.AlignmentFlag.AlignVCenter)
        bl.addLayout(row)
        lay.addWidget(band)

        self._section(lay, 'Your tools')
        grid = QGridLayout()
        grid.setSpacing(14)
        self.feature_cards: dict[str, FeatureCard] = {}
        for i, (key, icon_name, title, desc) in enumerate(FEATURES):
            fc = FeatureCard(key, icon_name, title, desc)
            self._icon_tiles.append(fc.tile)
            fc.open_button.clicked.connect(lambda _=False, k=key: self._navigate(k))
            fc.demo_button.clicked.connect(lambda _=False, k=key: self._open_demo_lab(k))
            grid.addWidget(fc, 0, i)
            self.feature_cards[key] = fc
        lay.addLayout(grid)

        self._section(lay, 'Quick comfort', 'Changes apply to every AccessShift window straight away.')
        quick, ql = card(margins=8, spacing=0)
        text_row = QHBoxLayout()
        text_row.setContentsMargins(12, 10, 10, 10)
        text_row.setSpacing(10)
        tl = QVBoxLayout()
        tl.setSpacing(4)
        tl.addWidget(label('Text size', 'cardTitle'))
        tl.addWidget(label('Make every page easier to read.', 'bodyText', True))
        text_row.addLayout(tl, 1)
        smaller = button('A-', 'secondaryButton')
        smaller.setAccessibleName('Smaller text')
        smaller.setFixedWidth(52)
        smaller.clicked.connect(lambda: self._step_font(-10))
        bigger = button('A+', 'secondaryButton')
        bigger.setAccessibleName('Larger text')
        bigger.setFixedWidth(52)
        bigger.clicked.connect(lambda: self._step_font(10))
        self.quick_font_value = label('110 %', 'valuePill')
        self.quick_font_value.setMinimumWidth(64)
        self.quick_font_value.setAlignment(Qt.AlignmentFlag.AlignCenter)
        text_row.addWidget(smaller)
        text_row.addWidget(self.quick_font_value)
        text_row.addWidget(bigger)
        ql.addLayout(text_row)
        for kind, key, heading, details in (
            ('option', 'word_highlight', 'Word highlighting', 'Highlights the word under your pointer to help you keep your place.'),
            ('theme', 'high_contrast', 'High contrast', 'Light text on a dark background with strong outlines.'),
            ('tint', 'tint', 'Screen tint', 'A soft colour wash over AccessShift windows to ease glare.'),
        ):
            ql.addWidget(divider())
            if kind == 'theme':
                r = PreferenceRow(heading, details, framed=False)
                r.layout().setContentsMargins(12, 10, 10, 10)
                r.changed.connect(lambda on: self._change_option('color_profile', 'high_contrast' if on else 'standard'))
                self.quick_contrast_row = r
            else:
                r = self._bind_row(kind, key, heading, details, framed=False)
                r.layout().setContentsMargins(12, 10, 10, 10)
            ql.addWidget(r)
        lay.addWidget(quick)
        lay.addStretch()
        return page

    def _step_font(self, delta: int) -> None:
        self._change_option('font_size_pct', max(90, min(160, self.prefs.font_size_pct + delta)))

    # ------------------------------------------------------------------ Profile
    def _page_personalize(self):
        page, lay = self._page('My accessibility profile',
                               'Choose a starting point, then fine-tune it. These are preferences, not diagnoses, '
                               'and everything is saved as you go.', icon_name='profile')
        self._section(lay, 'Choose a starting point', 'Each profile switches on a set of tools. You can change any of them below.')
        grid = QGridLayout()
        grid.setSpacing(14)
        for i, (key, p) in enumerate(PROFILES.items()):
            tile = self._tile(PROFILE_ICONS.get(key, 'profile'), 44)
            cardw = ChoiceCard(p['label'], p['description'], PROFILE_CHIPS.get(key, ()), tile)
            cardw.clicked.connect(lambda _=False, k=key: self._apply_profile(k))
            grid.addWidget(cardw, i // 2, i % 2)
            self._preset_buttons[key] = cardw
        lay.addLayout(grid)

        self._section(lay, 'Fine-tune your tools', 'Click a row or its switch to turn a tool on or off.')
        tools, tl = card(margins=8, spacing=0)
        rows = (
            ('module', 'gaze_control', 'Hands-free control',
             'Point with your head or eyes using your webcam. Turning this on starts the camera.'),
            ('option', 'blink_select', 'Blink to select',
             'In hands-free control, a slow blink chooses the option you are pointing at.'),
            ('module', 'steady_hand', 'SteadyHand',
             'Smooth shaky pointer movement and make small targets easier to hit.'),
            ('module', 'smart_interface', 'SmartInterface',
             'Use larger text, calmer colours and simpler layouts in the healthcare demo.'),
            ('option', 'reduce_complexity', 'Simplified, step-by-step layout',
             'Hide clutter and show forms one step at a time.'),
            ('option', 'word_highlight', 'Word highlighting',
             'Highlight the word under your pointer. Helpful for focus, including for many people with ADHD.'),
        )
        for i, (kind, key, heading, details) in enumerate(rows):
            if i:
                tl.addWidget(divider())
            r = self._bind_row(kind, key, heading, details, framed=False)
            r.layout().setContentsMargins(14, 12, 12, 12)
            tl.addWidget(r)
        lay.addWidget(tools)
        actions = QHBoxLayout()
        actions.addStretch()
        done = button('Save and go to my dashboard', 'primaryButton')
        done.setMinimumHeight(48)
        done.clicked.connect(self._finish_setup)
        actions.addWidget(done)
        lay.addLayout(actions)
        lay.addStretch()
        return page

    # ------------------------------------------------------------------ Head movement
    def _speed_choices(self, store: dict) -> QHBoxLayout:
        choices = QHBoxLayout()
        choices.setSpacing(12)
        for key, name, ms in self.HEAD_SPEEDS:
            b = button(f'{name}  ·  {ms / 1000:g} s', 'presetButton')
            b.setCheckable(True)
            b.setMinimumHeight(54)
            b.clicked.connect(lambda _=False, ms=ms: self._change_option('gaze_dwell_ms', ms))
            store[key] = b
            choices.addWidget(b)
        return choices

    def _steps_card(self, title: str, steps) -> QFrame:
        box, st = card(spacing=14)
        st.addWidget(label(title, 'sectionTitle'))
        for number, step_title, text in steps:
            row = QHBoxLayout()
            row.setSpacing(14)
            row.addWidget(label(number, 'number'), 0, Qt.AlignmentFlag.AlignTop)
            text_col = QVBoxLayout()
            text_col.setSpacing(2)
            text_col.addWidget(label(step_title, 'cardTitle'))
            text_col.addWidget(label(text, 'bodyText', True))
            row.addLayout(text_col, 1)
            st.addLayout(row)
        return box

    def _page_gaze(self):
        page, lay = self._page('Head movement control',
                               'Point by turning your head, or with your eyes. Hold still or blink slowly to choose. '
                               'Only your webcam is needed.', icon_name='head')
        self.gaze_notice = label('', 'warningPill', True)  # why hands-free stopped, if it did
        self.gaze_notice.hide()
        lay.addWidget(self.gaze_notice)

        start_box, sb = card(margins=24, spacing=12)
        sb.addWidget(label('Point with', 'sectionTitle'))
        choices = QHBoxLayout()
        choices.setSpacing(12)
        self._pointing_cards = {}
        self._pointing = self._gaze_source()
        for source, icon_name, title, desc in (
            ('head', 'head', 'My head', 'Turn your head toward an option. The steadiest choice on most laptop webcams.'),
            ('eyes', 'eye', 'My eyes', 'Point with eye movement and blink to select. Needs good light on your face.'),
        ):
            choice = ChoiceCard(title, desc, (), self._tile(icon_name, 44))
            choice.clicked.connect(lambda _=False, src=source: self._choose_pointing(src))
            self._pointing_cards[source] = choice
            choices.addWidget(choice)
        sb.addLayout(choices)
        self.gaze_toggle = HeadStartButton('Start head control', 'Stop head control')
        self.gaze_toggle.clicked.connect(lambda: self._toggle_gaze(self._pointing))
        sb.addWidget(self.gaze_toggle)
        sb.addWidget(label('Opens the hands-free appointment booking demo full screen. Use Quit hands-free in its top '
                           'bar to leave at any time, or close your eyes for 5 seconds.', 'bodyText', True))
        lay.addWidget(start_box)
        lay.addWidget(self._steps_card('How it works', (
            ('1', 'Set up', 'With your head: turn when the arrows ask. With your eyes: look at each dot as it appears.'),
            ('2', 'Choose', 'Point at an option. Hold still until the ring fills, or blink slowly to choose it.'),
            ('3', 'Finish', 'After booking, choose Start over or Close. Or press Quit hands-free whenever you like.'),
        )))
        speed, sp = card(spacing=10)
        sp.addWidget(label('Selection', 'sectionTitle'))
        sp.addWidget(self._bind_row('option', 'blink_select', 'Blink to select',
                                    'A slow, deliberate blink chooses the option you are pointing at.', framed=False))
        sp.addWidget(label('Selection speed', 'cardTitle'))
        sp.addWidget(label('How long to hold still before an option is chosen.', 'bodyText', True))
        self._dwell_buttons = {}
        sp.addLayout(self._speed_choices(self._dwell_buttons))
        lay.addWidget(speed)
        tips, tp = card(name='innerCard')
        tp.addWidget(label('For the best tracking', 'cardTitle'))
        tp.addWidget(label('Sit about an arm\'s length from the screen and light your face from the front. If eye '
                           'pointing drifts, use Recalibrate in the full-screen view or switch to your head.',
                           'bodyText', True))
        lay.addWidget(tips)
        lay.addStretch()
        return page

    def _choose_pointing(self, source: str) -> None:
        if self.prefs.gaze_control and self._gaze_source() != source:
            self._start_gaze(source)  # running: switch the live session (it recalibrates)
        self._pointing = source
        self._refresh()

    # ------------------------------------------------------------------ SteadyHand
    def _page_steady(self):
        page, lay = self._page(
            'SteadyHand',
            'Softens Parkinsonian tremor on the pointer and quietly records a motor session you can share with a clinician.',
            icon_name='steady',
        )

        intro, il = card(spacing=10)
        il.addWidget(label(
            'Everyday portals ask for precise clicks that a 4 to 7 Hz tremor often cannot deliver, especially when '
            'medication wears toward OFF. SteadyHand filters that motion, widens click targets, and guards against '
            'accidental drags, using only the mouse you already have.',
            'bodyText', True,
        ))
        lay.addWidget(intro)

        self.steady_toggle = self._bind_row(
            'module', 'steady_hand', 'Use SteadyHand',
            'Applies stabilization across AccessShift while the session chart below keeps updating.',
        )
        lay.addWidget(self.steady_toggle)

        demo, dl = card(spacing=12)
        dl.addWidget(label('Try it', 'sectionTitle'))
        dl.addWidget(label(
            'Work through the booking steps on the canvas, starting with Baseline and then Full assist so you can '
            'feel the difference in accuracy and effort.',
            'bodyText', True,
        ))
        self.steady_panel = SteadyHandTrialPanel(
            self.steady, self.prefs.target_size_pct, self.repo_root, self.prefs.as_dict(),
        )
        self.playground = self.steady_panel.playground
        dl.addWidget(self.steady_panel)
        lay.addWidget(demo)

        config, cfg = card(spacing=8)
        cfg.addWidget(label('Assist settings', 'sectionTitle'))
        cfg.addWidget(label('Stabilization strength', 'cardTitle'))
        cfg.addWidget(label(
            'How firmly tremor-band motion is filtered. Values above 100% keep leaning harder on the smoother.',
            'bodyText', True,
        ))
        self.strength_slider, sr = self._slider(0, 200, 5, 'tremor_strength', '%', ('Light', 'Maximum'))
        cfg.addLayout(sr)
        cfg.addSpacing(8)
        cfg.addWidget(label('Simulated tremor intensity', 'cardTitle'))
        cfg.addWidget(label(
            'How strong the demo tremor feels on the canvas when simulation is on, from mild through intense.',
            'bodyText', True,
        ))
        self.intensity_slider, ir = self._slider(0, 100, 5, 'tremor_intensity', '%', ('Mild', 'Intense'))
        cfg.addLayout(ir)
        cfg.addSpacing(8)
        cfg.addWidget(label('Click zone size', 'cardTitle'))
        cfg.addWidget(label(
            'Expands how close the pointer needs to be before a booking step still counts.',
            'bodyText', True,
        ))
        self.target_slider, tr = self._slider(100, 200, 10, 'target_size_pct', '%', ('Normal', 'Large'))
        cfg.addLayout(tr)
        lay.addWidget(config)
        lay.addStretch()
        return page

    # ------------------------------------------------------------------ SmartInterface
    def _page_interface(self):
        page, lay = self._page('SmartInterface',
                               'Make AccessShift easier to read and calmer to look at. Every change applies to all '
                               'AccessShift windows instantly.', icon_name='interface')
        self.interface_toggle = self._bind_row('module', 'smart_interface', 'Use SmartInterface on the healthcare form',
                                               'Turn the busy sample appointment form into a simpler, clearer one.')
        lay.addWidget(self.interface_toggle)

        reading, rl = card(spacing=8)
        rl.addWidget(label('Reading', 'sectionTitle'))
        rl.addWidget(label('Text size', 'cardTitle'))
        self.font_slider, fr = self._slider(90, 160, 10, 'font_size_pct', '%', ('Smaller', 'Larger'))
        rl.addLayout(fr)
        rl.addSpacing(6)
        rl.addWidget(label('Letter spacing', 'cardTitle'))
        self.spacing_slider, spacing_row = self._slider(0, 4, 1, 'letter_spacing_px', 'px', ('Normal', 'Wide'))
        rl.addLayout(spacing_row)
        rl.addSpacing(4)
        rl.addWidget(divider())
        self.highlight_row = self._bind_row('option', 'word_highlight', 'Word highlighting',
                                            'Highlights the word under your pointer so it is easier to keep your '
                                            'place while reading. Helpful for many people with ADHD.', framed=False)
        rl.addWidget(self.highlight_row)
        rl.addWidget(divider())
        self.simple_row = self._bind_row('option', 'reduce_complexity', 'Simplified, step-by-step layout',
                                         'Hide clutter and show the healthcare form one step at a time.', framed=False)
        rl.addWidget(self.simple_row)
        lay.addWidget(reading)

        colours, cl = card(spacing=10)
        cl.addWidget(label('Colour theme', 'sectionTitle'))
        cl.addWidget(label('Pick the look that is most comfortable for your eyes.', 'bodyText', True))
        swatches = QHBoxLayout()
        swatches.setSpacing(12)
        self._theme_buttons = {}
        for key, name in theme_mod.THEME_LABELS:
            t = theme_mod.THEMES[key]
            sw = SwatchButton(name, (t.bg, t.primary, t.mint if key != 'high_contrast' else t.text))
            sw.clicked.connect(lambda _=False, k=key: self._change_option('color_profile', k))
            self._theme_buttons[key] = sw
            swatches.addWidget(sw)
        cl.addLayout(swatches)
        lay.addWidget(colours)

        tint, tl = card(spacing=10)
        head = QHBoxLayout()
        head.setSpacing(14)
        head.addWidget(self._tile('tint', 40), 0, Qt.AlignmentFlag.AlignTop)
        ht = QVBoxLayout()
        ht.setSpacing(3)
        ht.addWidget(label('Screen tint', 'sectionTitle'))
        ht.addWidget(label('A soft colour wash that can reduce glare and visual stress. Pick a colour to turn it on.',
                           'bodyText', True))
        head.addLayout(ht, 1)
        self.tint_switch = Switch('Screen tint')
        self.tint_switch.toggled.connect(self._set_screen_tint)
        head.addWidget(self.tint_switch, 0, Qt.AlignmentFlag.AlignVCenter)
        tl.addLayout(head)
        tint_swatches = QHBoxLayout()
        tint_swatches.setSpacing(12)
        self._tint_buttons = {}
        for key, name in (('warm', 'Warm amber'), ('cool', 'Cool blue'), ('rose', 'Soft rose')):
            sw = SwatchButton(name, (TINT_COLORS[key],))
            sw.setMinimumHeight(76)
            sw.clicked.connect(lambda _=False, k=key: self._pick_tint(k))
            self._tint_buttons[key] = sw
            tint_swatches.addWidget(sw)
        tl.addLayout(tint_swatches)
        tl.addWidget(label('Strength', 'cardTitle'))
        self.tint_slider, tint_row = self._slider(0, 20, 1, 'tint_opacity', '%', ('Subtle', 'Strong'))
        tl.addLayout(tint_row)
        self.tint_status = label('Screen tint is off.', 'bodyText', True)
        tl.addWidget(self.tint_status)
        lay.addWidget(tint)

        demo, dl = card(name='band', margins=24, spacing=10)
        drow = QHBoxLayout()
        drow.setSpacing(18)
        drow.addWidget(self._tile('lab', 48), 0, Qt.AlignmentFlag.AlignTop)
        dt = QVBoxLayout()
        dt.setSpacing(4)
        dt.addWidget(label('SmartInterface demo', 'sectionTitle'))
        dt.addWidget(label('See your settings reshape a busy healthcare appointment form. Keep the demo open next to '
                           'this page and every change shows up there instantly.', 'bandText', True))
        drow.addLayout(dt, 1)
        open_demo = button('Open the demo', 'primaryButton')
        open_demo.clicked.connect(lambda: self._open_demo_lab('interface'))
        drow.addWidget(open_demo, 0, Qt.AlignmentFlag.AlignVCenter)
        dl.addLayout(drow)
        lay.addWidget(demo)
        lay.addStretch()
        return page

    def _slider(self, minimum, maximum, step, key, suffix, captions: tuple[str, str] | None = None):
        widget = QSlider(Qt.Orientation.Horizontal)
        widget.setRange(minimum, maximum)
        widget.setSingleStep(step)
        widget.setPageStep(step)
        widget.setCursor(Qt.CursorShape.PointingHandCursor)
        widget.setAccessibleName(key.replace('_', ' '))
        widget.valueChanged.connect(lambda value, k=key: self._change_option(k, value))
        value_label = label('', 'valuePill')
        value_label.setMinimumWidth(64)
        value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        row = QHBoxLayout()
        row.setSpacing(12)
        if captions:
            row.addWidget(label(captions[0], 'micro'))
        row.addWidget(widget, 1)
        if captions:
            row.addWidget(label(captions[1], 'micro'))
        row.addWidget(value_label)
        self._sliders[key] = (widget, value_label, suffix)
        return widget, row

    # ------------------------------------------------------------------ tint
    def _pick_tint(self, color: str) -> None:
        self._change_option('tint_color', color)
        if not self.tint_manager.active:
            self._set_screen_tint(True)

    def _set_screen_tint(self, enabled: bool) -> None:
        try:
            if enabled:
                if self.prefs.tint_opacity == 0:
                    self.prefs.tint_opacity = 10
                    self._save()
                self.tint_manager.update(color=self.prefs.tint_color, opacity=self.prefs.tint_opacity)
                self.tint_manager.enable()
            else:
                self.tint_manager.disable()
        except Exception as exc:
            self.tint_manager.disable()
            QMessageBox.warning(self, 'Screen tint unavailable',
                                'The tint could not be applied.\n\n' + str(exc))
        self._refresh()

    def _sync_tint_controls(self) -> None:
        active = self.tint_manager.active
        self.tint_switch.blockSignals(True)
        self.tint_switch.setChecked(active)
        self.tint_switch.blockSignals(False)
        self.tint_switch.update()
        for key, sw in self._tint_buttons.items():
            sw.setChecked(active and key == self.prefs.tint_color)
        names = {'warm': 'Warm amber', 'cool': 'Cool blue', 'rose': 'Soft rose'}
        self.tint_status.setText(
            f'{names.get(self.prefs.tint_color, "Tint")} tint is on at {self.prefs.tint_opacity}% in all AccessShift '
            'windows. Other apps are not affected.' if active else
            'Screen tint is off. Other apps are never affected.')

    # ------------------------------------------------------------------ appearance
    def _apply_visual_preferences(self) -> None:
        t = theme_mod.theme(self.prefs.color_profile)
        Switch.set_colors(t.active, '#8FA39C' if self.prefs.color_profile != 'high_contrast' else '#5B6B66',
                          '#FFFFFF', t.primary)
        self.setStyleSheet(theme_mod.stylesheet(self.prefs.font_size_pct, self.prefs.color_profile))
        theme_mod.apply_letter_spacing(self.prefs.letter_spacing_px)
        for tile in self._icon_tiles:
            tile.set_colors(t.mint, t.primary)
        for tile in [self.brand_mark] + self._brand_tiles:
            tile.set_colors(t.primary, t.on_primary)
        for b, name in self._nav_icons:
            color = t.sidebar_text if b.objectName() == 'navButton' else t.heading
            if b.objectName() == 'profileButton' and b.isChecked():
                color = t.on_primary
            b.setIcon(icons.icon(name, color, 20))
        for b, name in getattr(self, '_home_feature_links', []):
            b.setIcon(icons.icon(name, t.primary, 20))
        if hasattr(self, '_explore_button'):
            self._explore_button.setIcon(icons.icon('arrow', t.on_primary, 22))
        for art in self._themed_art:
            art.set_theme(t)
        for key, sw in getattr(self, '_theme_buttons', {}).items():
            sw.setChecked(key == self.prefs.color_profile)
            sw.set_caption_color(t.heading)
        for sw in getattr(self, '_tint_buttons', {}).values():
            sw.set_caption_color(t.heading)
        if hasattr(self, 'steady_panel'):
            self.steady_panel.set_theme(t)
        for sw in self.findChildren(Switch):
            sw.update()
        self.highlighter.set_color(t.highlight)
        self.highlighter.set_enabled(bool(getattr(self.prefs, 'word_highlight', False)))
        self.tint_manager.update(color=self.prefs.tint_color, opacity=self.prefs.tint_opacity)

    def closeEvent(self, event):
        self.tint_manager.disable()
        self.highlighter.set_enabled(False)
        super().closeEvent(event)

    # ------------------------------------------------------------------ navigation
    def _navigate(self, key):
        if hasattr(self, 'steady_panel') and self.steady_panel.trial_running and key != 'steady':
            self.steady_panel.abort_trial()
        self.stack.setCurrentWidget(self._pages[key])
        for k, btn in self._nav.items():
            btn.setChecked(k == key)
        immersive = key in ('home', 'intro')
        self.sidebar.setVisible(not immersive)
        self.top_bar.setVisible(not immersive)
        self.footer.setVisible(not immersive)
        self.top_title.setText(PAGE_TITLES.get(key, ''))
        was = self.profile_button.isChecked()
        self.profile_button.setChecked(key == 'personalize')
        if was != self.profile_button.isChecked() and hasattr(self, 'brand_mark'):
            self._apply_profile_icon()

    def _apply_profile_icon(self) -> None:
        t = theme_mod.theme(self.prefs.color_profile)
        self.profile_button.setIcon(icons.icon('profile', t.on_primary if self.profile_button.isChecked() else t.heading, 20))

    def _finish_setup(self):
        self.prefs.initial_setup_complete = True
        self._save()
        self._navigate('overview')

    # ------------------------------------------------------------------ demos and hands-free hooks
    def _open_demo_lab(self, section: str = 'start') -> None:
        """Opens the Demo Lab window (provided by accessshift.ui.main_window.MainWindow)."""

    def _gaze_source(self) -> str:
        return 'head'

    def _start_gaze(self, source: str) -> None:
        self._change_module('gaze_control', True)

    def _toggle_gaze(self, source: str) -> None:
        if self.prefs.gaze_control and self._gaze_source() == source:
            self._change_module('gaze_control', False)
        else:
            self._start_gaze(source)

    # ------------------------------------------------------------------ preferences
    def _apply_profile(self, profile_id):
        p = PROFILES[profile_id]
        if profile_id != 'custom':
            self.prefs.profile = profile_id
            for key in MODULE_KEYS:
                setattr(self.prefs, key, bool(p[key]))
        else:
            self.prefs.profile = 'custom'
        self._apply_preferences_to_engine()
        self._save()
        self._refresh()

    def _apply_preferences_to_engine(self):
        previous = self._syncing_engine
        self._syncing_engine = True
        try:
            self.engine.set_profile(self.prefs.profile)
            for key in MODULE_KEYS:
                self.engine.set_module(key, getattr(self.prefs, key))
        finally:
            self._syncing_engine = previous
        self.steady.strength = self.prefs.tremor_strength / 100.0
        self.steady.tremor_intensity = self.prefs.tremor_intensity
        self.steady.enabled = self.prefs.steady_hand and self.prefs.assistance_enabled

    def _on_external_modules_changed(self, flags):
        """Follow updates sent by other team members through AdaptiveEngine."""
        if self._syncing_engine:
            return
        self.prefs.profile = self.engine.profile.id
        for key in MODULE_KEYS:
            setattr(self.prefs, key, bool(getattr(flags, key)))
        self.steady.enabled = self.prefs.steady_hand and self.prefs.assistance_enabled
        self._save()
        self._refresh()

    def _change_module(self, key, value):
        setattr(self.prefs, key, bool(value))
        # A user can tweak a preset without losing its selected options.
        self.prefs.profile = 'custom'
        self._apply_preferences_to_engine()
        self._save()
        self._refresh()

    def _change_option(self, key, value):
        setattr(self.prefs, key, int(value) if isinstance(value, int) and not isinstance(value, bool) else value)
        if key == 'tremor_strength':
            self.steady.strength = self.prefs.tremor_strength / 100.0
        if key == 'tremor_intensity':
            self.steady.tremor_intensity = self.prefs.tremor_intensity
            self.steady.new_tremor_pattern()
        if key == 'target_size_pct' and hasattr(self, 'steady_panel'):
            self.steady_panel.set_target_size(self.prefs.target_size_pct)
        self._save()
        if key == 'tint_opacity' and value and not self.tint_manager.active:
            self._set_screen_tint(True)  # moving the strength slider turns the tint on
            return
        self._refresh()

    def _save(self):
        save_settings(self.prefs)
        if hasattr(self, 'steady_panel'):
            self.steady_panel.set_extra(self.prefs.as_dict())
        self.preferences_changed.emit(self.prefs.as_dict())

    def _refresh(self):
        name = 'Custom mix' if self.prefs.profile == 'custom' else PROFILES.get(self.prefs.profile, PROFILES['custom'])['label']
        self.overview_profile.setText(f'Your profile: {name}')
        theme_name = dict(theme_mod.THEME_LABELS).get(self.prefs.color_profile, 'Standard')
        self.overview_summary.setText(
            f'SteadyHand is {"on" if self.prefs.steady_hand else "off"}, SmartInterface is '
            f'{"on" if self.prefs.smart_interface else "off"}, and text is at {self.prefs.font_size_pct}% '
            f'with the {theme_name} colour theme.')
        source = self._gaze_source()
        speed = next((n for _k, n, ms in self.HEAD_SPEEDS if ms == self.prefs.gaze_dwell_ms), 'Custom')
        cards = self.feature_cards
        running = bool(self.prefs.gaze_control)
        if running:
            self._pointing = source  # the buttons always show what is really running
        cards['gaze'].set_status('Running' if running else 'Ready', running)
        cards['gaze'].meta.setText(
            f'Pointing with your {self._pointing}, speed {speed} ({self.prefs.gaze_dwell_ms / 1000:g} s), '
            f'blink to select {"on" if self.prefs.blink_select else "off"}')
        cards['steady'].set_status('On' if self.prefs.steady_hand else 'Off', self.prefs.steady_hand)
        cards['steady'].meta.setText(
            f'Smoothing {self.prefs.tremor_strength}%, tremor intensity {self.prefs.tremor_intensity}, '
            f'click zones {self.prefs.target_size_pct}%'
        )
        cards['interface'].set_status('On' if self.prefs.smart_interface else 'Off', self.prefs.smart_interface)
        cards['interface'].meta.setText(
            f'Text {self.prefs.font_size_pct}%, spacing {self.prefs.letter_spacing_px} px, {theme_name} colours')
        self.quick_font_value.setText(f'{self.prefs.font_size_pct} %')
        self.quick_contrast_row.set_value(self.prefs.color_profile == 'high_contrast')
        for k, btn in self._preset_buttons.items():
            btn.setChecked(k == self.prefs.profile)
        for kind, key, row in self._bound_rows:
            row.set_value(self.tint_manager.active if kind == 'tint' else bool(getattr(self.prefs, key, False)))
        noun = 'head' if self._pointing == 'head' else 'eye'
        self.gaze_toggle.set_texts(f'Start {noun} control', f'Stop {noun} control')
        self.gaze_toggle.set_value(running)
        for src, choice in self._pointing_cards.items():
            choice.setChecked(src == self._pointing)
        for key, _name, ms in self.HEAD_SPEEDS:
            self._dwell_buttons[key].setChecked(self.prefs.gaze_dwell_ms == ms)
        for k, (slider, text, suffix) in self._sliders.items():
            value = int(getattr(self.prefs, k))
            slider.blockSignals(True)
            slider.setValue(value)
            slider.blockSignals(False)
            text.setText(f'{value} {suffix}')
        self._sync_tint_controls()
        self.footer_status.setText('Settings saved on this device')
        self._apply_visual_preferences()

    def _request_calibration(self):
        self.calibration_requested.emit()
