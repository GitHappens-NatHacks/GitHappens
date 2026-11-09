"""Younify control center: preferences-first desktop UI for macOS and Windows.

A 3-second Home splash (logo and tagline) leads to the Dashboard. A horizontal top
navigation bar holds Home, Dashboard and the three features in a fixed order
(SteadyHand, Head movement, SmartInterface), plus the Demo Lab and the
accessibility profile. It uses the existing AdaptiveEngine and SteadyHandController
APIs unchanged.
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, QRectF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QLinearGradient, QPainter, QPainterPath
from PySide6.QtWidgets import (
    QApplication, QFrame, QGraphicsOpacityEffect, QGridLayout, QHBoxLayout, QLabel, QMainWindow,
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
    PROFILES, AccessibilitySettings, load_settings, save_settings,
)
from accessshift.ui.steadyhand_panel import LABELS, SEQUENCE, SteadyHandTrialPanel, TremorPlayground  # noqa: F401

MODULE_KEYS = ('gaze_control', 'steady_hand', 'smart_interface', 'predictive_speech')
APP_NAME = 'Younify'
TAGLINE = 'Everyday access, quietly assisted'
SPLASH_MS = 2000  # the Home splash, then the Dashboard

# The three Younify features, in the order they appear everywhere.
FEATURES = (
    ('steady', 'steady', 'SteadyHand', 'Pointer stabilization and a clinic-ready motor session.'),
    ('gaze', 'head', 'Head movement', 'Point with your head. Blink to select. Webcam only.'),
    ('interface', 'interface', 'SmartInterface', 'Larger text, calmer colour, simpler screens.'),
)
# One photograph per tab (team photo set in assets/ui).
PHOTOS = {
    'overview': 'desk.jpg', 'profile': 'quiet-chair.jpg', 'steady': 'mouse-mat.jpg',
    'head': 'webcam.jpg', 'interface': 'glasses-notes.jpg',
}

PROFILE_CHIPS = {
    'als': ('Head movement', 'Blink to select', 'SmartInterface'),
    'parkinsons': ('SteadyHand', 'SmartInterface'),
    'cognitive': ('SmartInterface', 'Simplified layout'),
    'custom': ('Any combination',),
}
PROFILE_ICONS = {'als': 'head', 'parkinsons': 'steady', 'cognitive': 'interface', 'custom': 'profile'}
PROFILE_ORDER = ('parkinsons', 'als', 'cognitive', 'custom')  # SteadyHand, Head movement, SmartInterface, custom


class Photo(QWidget):
    """A photograph, cropped to fill, with rounded corners and an optional shade for text."""

    def __init__(self, file_name: str, *, height: int = 150, radius: int = 16, top_only: bool = False,
                 shade: bool = False):
        super().__init__()
        self.image = theme_mod.pixmap('ui', file_name)
        self.radius = radius
        self.top_only = top_only
        self.shade = shade
        self.shade_color = QColor(theme_mod.LOGO_GREEN)
        self.setMinimumHeight(height)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed if not shade else QSizePolicy.Policy.Preferred)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, False)

    def set_shade(self, color: str) -> None:
        self.shade_color = QColor(color)
        self.update()

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        rect = QRectF(self.rect())
        path = QPainterPath()
        r = self.radius
        if self.top_only:
            path.moveTo(rect.left(), rect.bottom())
            path.lineTo(rect.left(), rect.top() + r)
            path.quadTo(rect.left(), rect.top(), rect.left() + r, rect.top())
            path.lineTo(rect.right() - r, rect.top())
            path.quadTo(rect.right(), rect.top(), rect.right(), rect.top() + r)
            path.lineTo(rect.right(), rect.bottom())
            path.closeSubpath()
        else:
            path.addRoundedRect(rect, r, r)
        p.setClipPath(path)
        if self.image.isNull():
            p.fillRect(rect, QColor(theme_mod.SOFT_MINT))
        else:
            img = self.image
            scale = max(rect.width() / img.width(), rect.height() / img.height())
            sw, sh = rect.width() / scale, rect.height() / scale
            src = QRectF((img.width() - sw) / 2, (img.height() - sh) / 2, sw, sh)
            p.drawPixmap(rect, img, src)
        if self.shade:
            grad = QLinearGradient(rect.topLeft(), rect.topRight())
            for stop, alpha in ((0.0, 0.92), (0.55, 0.62), (1.0, 0.05)):
                c = QColor(self.shade_color)
                c.setAlphaF(alpha)
                grad.setColorAt(stop, c)
            p.fillRect(rect, grad)
        p.end()


class PhotoHeader(Photo):
    """Page header: the tab's photograph with its title (and optional line) on a soft shade."""

    def __init__(self, file_name: str, title: str, subtitle: str = ''):
        super().__init__(file_name, height=168 if subtitle else 150, radius=10, shade=True)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(36, 28, 36, 28)
        lay.setSpacing(8)
        lay.addStretch(1)
        self.title = label(title, 'bannerTitle', True)
        lay.addWidget(self.title)
        if subtitle:
            sub = label(subtitle, 'bannerText', True)
            sub.setWordWrap(True)
            lay.addWidget(sub)
        lay.addStretch(1)


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
    """Dashboard entry for one feature: its photo, what it does, live status and two actions."""

    def __init__(self, key: str, icon_name: str, title: str, description: str):
        super().__init__()
        self.setObjectName('card')
        self.key = key
        outer = QVBoxLayout(self)
        outer.setContentsMargins(1, 1, 1, 1)
        outer.setSpacing(0)
        self.photo = Photo(PHOTOS.get(icon_name, 'desk.jpg'), height=150, radius=10, top_only=True)
        outer.addWidget(self.photo)
        body = QVBoxLayout()
        body.setContentsMargins(22, 18, 22, 18)
        body.setSpacing(10)
        top = QHBoxLayout()
        top.setSpacing(10)
        top.addWidget(label(title, 'featureTitle', True), 1, Qt.AlignmentFlag.AlignVCenter)
        self.status = label('Off', 'pill')
        top.addWidget(self.status, 0, Qt.AlignmentFlag.AlignVCenter)
        body.addLayout(top)
        self.desc = label(description, 'featureDesc', True)
        body.addWidget(self.desc)
        self.meta = label('', 'featureMeta', True)
        body.addWidget(self.meta)
        body.addStretch(1)
        actions = QHBoxLayout()
        actions.setSpacing(8)
        self.open_button = button('Open', 'secondaryButton')
        self.open_button.setAccessibleName(f'Open {title}')
        self.demo_button = button('Demo', 'linkButton')
        self.demo_button.setAccessibleName(f'Try the {title} demo')
        actions.addWidget(self.open_button)
        actions.addWidget(self.demo_button)
        actions.addStretch(1)
        body.addLayout(actions)
        outer.addLayout(body, 1)
        self.tile = icons.IconTile(icon_name, 44)  # kept for theming code; not shown on the card

    def set_status(self, text: str, good: bool) -> None:
        self.status.setText(text)
        self.status.setObjectName('goodPill' if good else 'pill')
        self.status.style().unpolish(self.status)
        self.status.style().polish(self.status)


class QuickTile(QFrame):
    """Quick comfort control: an icon, the setting's name and its control. No extra text."""

    def __init__(self, icon_name: str, title: str, control: QWidget):
        super().__init__()
        self.setObjectName('quickTile')
        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 18, 20, 18)
        lay.setSpacing(14)
        top = QHBoxLayout()
        top.setSpacing(12)
        self.tile = icons.IconTile(icon_name, 38)
        top.addWidget(self.tile)
        top.addWidget(label(title, 'cardTitle', True), 1)
        lay.addLayout(top)
        lay.addStretch(1)
        lay.addWidget(control, 0, Qt.AlignmentFlag.AlignLeft)


class MainWindow(QMainWindow):
    """Drop-in replacement for accessshift.ui.main_window.MainWindow(repo_root)."""

    preferences_changed = Signal(object)  # dict; app services may subscribe
    calibration_requested = Signal()  # gaze team can connect worker/controller
    assistance_changed = Signal(bool)

    # Hands-free selection speed: Relaxed 1.6 s, Normal 1.1 s, Quick 0.8 s.
    HEAD_SPEEDS = (('relaxed', 'Relaxed', 1600), ('normal', 'Normal', 1100), ('quick', 'Quick', 800))

    def __init__(self, repo_root: Path):
        super().__init__()
        theme_mod.clear_pixmap_cache()
        self.repo_root = Path(repo_root)
        self.prefs = load_settings()
        self.engine = AdaptiveEngine(self)
        self.steady = SteadyHandController()
        self.speech = None
        self._nav = {}
        self._pages = {}
        self._bound_rows: list[tuple[str, str, PreferenceRow]] = []  # (kind, key, row)
        self._quick_switches: list[tuple[str, Switch]] = []
        self._sliders = {}
        self._preset_buttons = {}
        self._icon_tiles: list[icons.IconTile] = []
        self._photo_headers: list[PhotoHeader] = []
        self._nav_icons: list[tuple[QPushButton, str]] = []
        self._animations: list = []
        self.tint_manager = ScreenTintManager(QApplication.instance())
        self._splash_timer = QTimer(self)
        self._splash_timer.setSingleShot(True)
        self._splash_timer.timeout.connect(self._leave_splash)
        self._syncing_engine = True
        self._build_ui()
        self.tint_manager.register_window(self)  # Restrict tint to this application window
        self.engine.modules_changed.connect(self._on_external_modules_changed)
        self._apply_preferences_to_engine()
        self._syncing_engine = False
        self._refresh()
        self._navigate('home')
        self.resize(1280, 840)
        self.setMinimumSize(1040, 680)
        self.setWindowTitle(APP_NAME)
        self.setWindowIcon(theme_mod.logo_icon())

    # ------------------------------------------------------------------ shell
    def _build_ui(self):
        root = QWidget()
        root.setObjectName('appRoot')
        self.setCentralWidget(root)
        outer = QVBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        nav = QFrame()
        nav.setObjectName('topNav')
        self.top_nav = nav
        self.top_bar = nav
        nl = QHBoxLayout(nav)
        nl.setContentsMargins(24, 12, 20, 12)
        nl.setSpacing(4)
        brand = QPushButton(APP_NAME)
        brand.setObjectName('navBrand')
        brand.setCursor(Qt.CursorShape.PointingHandCursor)
        brand.setIcon(theme_mod.logo_icon())
        brand.setIconSize(QSize(40, 29))
        brand.setAccessibleName(f'{APP_NAME} dashboard')
        brand.clicked.connect(lambda: self._navigate('overview'))
        self.brand_button = brand
        nl.addWidget(brand)
        nl.addSpacing(12)
        tabs = [('overview', 'dashboard', 'Dashboard')]  # the Home splash shows only at launch
        tabs += [(key, icon_name, title) for key, icon_name, title, _ in FEATURES]
        for key, icon_name, text in tabs:
            tab = button(text, 'navTab')
            tab.setCheckable(True)
            tab.setMinimumHeight(40)
            tab.setAccessibleName(text)
            tab.clicked.connect(lambda _=False, k=key: self._navigate(k))
            self._nav_icons.append((tab, icon_name))
            nl.addWidget(tab)
            self._nav[key] = tab
        nl.addStretch(1)
        self._demo_shortcut = button('Demo Lab', 'navAction')
        self._demo_shortcut.setAccessibleName('Open Demo Lab')
        self._demo_shortcut.setToolTip(f'Open the Demo Lab: every {APP_NAME} feature in one window')
        self._demo_shortcut.setMinimumHeight(40)
        self._demo_shortcut.clicked.connect(lambda: self._open_demo_lab('start'))
        self._nav_icons.append((self._demo_shortcut, 'lab'))
        nl.addWidget(self._demo_shortcut)
        nl.addSpacing(6)
        self.profile_button = self._make_profile_button()
        nl.addWidget(self.profile_button)
        self.top_bar_layout = nl
        outer.addWidget(nav)

        self.stack = QStackedWidget()
        outer.addWidget(self.stack, 1)
        for key, method in [
            ('home', self._page_home),
            ('overview', self._page_overview),
            ('personalize', self._page_personalize),
            ('steady', self._page_steady),
            ('gaze', self._page_gaze),
            ('interface', self._page_interface),
        ]:
            page = method()
            self._pages[key] = page
            self.stack.addWidget(page)
        foot = QFrame()
        foot.setObjectName('footerBar')
        self.footer = foot
        fl = QHBoxLayout(foot)
        fl.setContentsMargins(32, 8, 32, 8)
        fl.addWidget(label(APP_NAME, 'footerText'))
        fl.addStretch()
        self.footer_status = label('Settings saved on this device', 'footerText')
        fl.addWidget(self.footer_status)
        outer.addWidget(foot)

    def _make_profile_button(self) -> QPushButton:
        b = button('My profile', 'profileButton')
        b.setCheckable(True)
        b.setMinimumHeight(40)
        b.setAccessibleName('My accessibility profile')
        b.setToolTip('My accessibility profile')
        b.clicked.connect(lambda: self._navigate('personalize'))
        self._nav_icons.append((b, 'profile'))
        return b

    def _tile(self, name: str, size: int = 44) -> icons.IconTile:
        tile = icons.IconTile(name, size)
        self._icon_tiles.append(tile)
        return tile

    def _page(self, title, subtitle, *, icon_name: str | None = None, photo: str | None = None):
        scroller = QScrollArea()
        scroller.setWidgetResizable(True)
        scroller.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        container = QWidget()
        container.setObjectName('scrollContent')
        content = QVBoxLayout(container)
        content.setContentsMargins(48, 32, 48, 48)
        content.setSpacing(18)
        header = PhotoHeader(photo or PHOTOS.get(icon_name or '', 'desk.jpg'), title, subtitle)
        self._photo_headers.append(header)
        content.addWidget(header)
        content.addSpacing(10)
        scroller.setWidget(container)
        return scroller, content

    def _section(self, lay, title, subtitle=None):
        lay.addSpacing(14)
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

    # ------------------------------------------------------------------ Home (splash)
    def _page_home(self):
        page = QWidget()
        page.setObjectName('homeRoot')
        lay = QVBoxLayout(page)
        lay.setContentsMargins(48, 48, 48, 48)
        lay.setSpacing(0)
        lay.addStretch(1)
        self.home_logo = QLabel()
        self.home_logo.setObjectName('homeLogo')
        self.home_logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.home_logo.setAccessibleName(f'{APP_NAME} logo')
        lay.addWidget(self.home_logo, 0, Qt.AlignmentFlag.AlignHCenter)
        lay.addSpacing(34)
        self.home_tagline = label(TAGLINE, 'homeTagline')
        self.home_tagline.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(self.home_tagline, 0, Qt.AlignmentFlag.AlignHCenter)
        lay.addStretch(1)
        self._set_home_logo(300)
        page.mousePressEvent = lambda _e: self._leave_splash()  # a click skips the wait
        return page

    def _set_home_logo(self, height: int) -> None:
        ratio = self.devicePixelRatioF() or 1.0
        logo = theme_mod.pixmap('brand', 'younify-logo.png')
        if logo.isNull():
            self.home_logo.setText(APP_NAME)
            return
        scaled = logo.scaledToHeight(round(height * ratio), Qt.TransformationMode.SmoothTransformation)
        scaled.setDevicePixelRatio(ratio)
        self.home_logo.setPixmap(scaled)

    def _leave_splash(self) -> None:
        self._splash_timer.stop()
        if self.stack.currentWidget() is self._pages['home']:
            self._navigate('overview')
            self._fade_in(self.stack.currentWidget(), 450)

    def _fade_in(self, widget: QWidget, ms: int) -> None:
        effect = QGraphicsOpacityEffect(widget)
        widget.setGraphicsEffect(effect)
        anim = QPropertyAnimation(effect, b'opacity', self)
        anim.setDuration(ms)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        anim.finished.connect(lambda w=widget: w.setGraphicsEffect(None))
        anim.finished.connect(lambda a=anim: self._animations.remove(a) if a in self._animations else None)
        self._animations.append(anim)
        anim.start()

    # ------------------------------------------------------------------ Dashboard
    def _page_overview(self):
        page, lay = self._page(APP_NAME, '', photo=PHOTOS['overview'])
        band, bl = card(name='band', margins=26, spacing=8)
        row = QHBoxLayout()
        row.setSpacing(20)
        texts = QVBoxLayout()
        texts.setSpacing(6)
        self.overview_profile = label('Your profile: Custom mix', 'bandTitle', True)
        self.overview_summary = label('', 'bandText', True)
        texts.addWidget(self.overview_profile)
        texts.addWidget(self.overview_summary)
        row.addLayout(texts, 1)
        edit = button('Edit profile', 'primaryButton')
        edit.clicked.connect(lambda: self._navigate('personalize'))
        row.addWidget(edit, 0, Qt.AlignmentFlag.AlignVCenter)
        bl.addLayout(row)
        lay.addWidget(band)

        self._section(lay, 'Tools')
        grid = QGridLayout()
        grid.setSpacing(18)
        self.feature_cards: dict[str, FeatureCard] = {}
        for i, (key, icon_name, title, desc) in enumerate(FEATURES):
            fc = FeatureCard(key, icon_name, title, desc)
            fc.open_button.clicked.connect(lambda _=False, k=key: self._navigate(k))
            fc.demo_button.clicked.connect(lambda _=False, k=key: self._open_demo_lab(k))
            grid.addWidget(fc, 0, i)
            self.feature_cards[key] = fc
        lay.addLayout(grid)

        self._section(lay, 'Quick comfort')
        quick = QGridLayout()
        quick.setSpacing(18)
        size = QWidget()
        sl = QHBoxLayout(size)
        sl.setContentsMargins(0, 0, 0, 0)
        sl.setSpacing(8)
        smaller = button('A-', 'secondaryButton')
        smaller.setAccessibleName('Smaller text')
        smaller.setFixedWidth(50)
        smaller.clicked.connect(lambda: self._step_font(-10))
        bigger = button('A+', 'secondaryButton')
        bigger.setAccessibleName('Larger text')
        bigger.setFixedWidth(50)
        bigger.clicked.connect(lambda: self._step_font(10))
        self.quick_font_value = label('110 %', 'valuePill')
        self.quick_font_value.setMinimumWidth(66)
        self.quick_font_value.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sl.addWidget(smaller)
        sl.addWidget(self.quick_font_value)
        sl.addWidget(bigger)
        tiles = [QuickTile('text', 'Text size', size)]
        for kind, icon_name, title in (('contrast', 'interface', 'High contrast'),
                                       ('tint', 'tint', 'Screen tint')):
            sw = Switch(title)
            if kind == 'contrast':
                sw.toggled.connect(lambda on: self._change_option('color_profile', 'high_contrast' if on else 'standard'))
            else:
                sw.toggled.connect(self._set_screen_tint)
            self._quick_switches.append((kind, sw))
            tiles.append(QuickTile(icon_name, title, sw))
        for i, tile in enumerate(tiles):
            self._icon_tiles.append(tile.tile)
            quick.addWidget(tile, 0, i)
        lay.addLayout(quick)
        lay.addStretch()
        return page

    def _step_font(self, delta: int) -> None:
        self._change_option('font_size_pct', max(90, min(160, self.prefs.font_size_pct + delta)))

    # ------------------------------------------------------------------ Profile
    def _page_personalize(self):
        page, lay = self._page(
            'My accessibility profile',
            'Pick a starting point, then adjust. Preferences only. Saved as you go.',
            icon_name='profile',
        )
        self._section(lay, 'Starting point')
        grid = QGridLayout()
        grid.setSpacing(14)
        for i, key in enumerate(k for k in PROFILE_ORDER if k in PROFILES):
            p = PROFILES[key]
            tile = self._tile(PROFILE_ICONS.get(key, 'profile'), 44)
            cardw = ChoiceCard(p['label'], p['description'], PROFILE_CHIPS.get(key, ()), tile)
            cardw.clicked.connect(lambda _=False, k=key: self._apply_profile(k))
            grid.addWidget(cardw, i // 2, i % 2)
            self._preset_buttons[key] = cardw
        lay.addLayout(grid)

        self._section(lay, 'Tools')
        tools, tl = card(margins=8, spacing=0)
        rows = (
            ('module', 'steady_hand', 'SteadyHand',
             'Stabilize the pointer and widen click targets.'),
            ('module', 'gaze_control', 'Hands-free control',
             'Point with your head. Starts the camera when on.'),
            ('option', 'blink_select', 'Blink to select',
             'A slow blink chooses the option under the pointer.'),
            ('module', 'smart_interface', 'SmartInterface',
             'Larger text and simpler layouts in the healthcare demo.'),
            ('option', 'reduce_complexity', 'Step-by-step layout',
             'Show forms one step at a time.'),
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
        done = button('Save and continue', 'primaryButton')
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
        page, lay = self._page(
            'Head movement',
            'Point with your head. Hold still or blink to choose. Webcam only.',
            icon_name='head',
        )
        self.gaze_notice = label('', 'warningPill', True)  # why hands-free stopped, if it did
        self.gaze_notice.hide()
        lay.addWidget(self.gaze_notice)

        start_box, sb = card(margins=24, spacing=12)
        sb.addWidget(label('Try it', 'sectionTitle'))
        self.gaze_toggle = HeadStartButton('Start head control', 'Stop head control')
        self.gaze_toggle.clicked.connect(lambda: self._toggle_gaze('head'))
        sb.addWidget(self.gaze_toggle)
        sb.addWidget(label(
            'Opens the booking demo full screen. Quit from the top bar, or close your eyes for 5 seconds.',
            'bodyText', True,
        ))
        lay.addWidget(start_box)
        lay.addWidget(self._steps_card('How it works', (
            ('1', 'Set up', 'Face the screen. Follow the calibration arrows.'),
            ('2', 'Choose', 'Hold still until the ring fills, or blink slowly.'),
            ('3', 'Finish', 'Start over, Close, or Quit hands-free anytime.'),
        )))
        speed, sp = card(spacing=10)
        sp.addWidget(label('Selection', 'sectionTitle'))
        sp.addWidget(self._bind_row(
            'option', 'blink_select', 'Blink to select',
            'A slow blink chooses the option under the pointer.', framed=False,
        ))
        sp.addWidget(label('Hold time', 'cardTitle'))
        self._dwell_buttons = {}
        sp.addLayout(self._speed_choices(self._dwell_buttons))
        lay.addWidget(speed)
        tips, tp = card(name='innerCard')
        tp.addWidget(label('Tracking tip', 'cardTitle'))
        tp.addWidget(label(
            'Sit an arm\'s length away with light on your face. Recalibrate if the pointer drifts.',
            'bodyText', True,
        ))
        lay.addWidget(tips)
        lay.addStretch()
        return page

    # ------------------------------------------------------------------ SteadyHand
    def _page_steady(self):
        page, lay = self._page(
            'SteadyHand',
            'Filters tremor on the pointer. Records a motor session for clinic review.',
            icon_name='steady',
        )

        self.steady_toggle = self._bind_row(
            'module', 'steady_hand', 'Use SteadyHand',
            'Stabilization on across Younify. Session chart updates below.',
        )
        lay.addWidget(self.steady_toggle)

        demo, dl = card(spacing=12)
        dl.addWidget(label('Practice', 'sectionTitle'))
        self.steady_panel = SteadyHandTrialPanel(
            self.steady, self.prefs.target_size_pct, self.repo_root, self.prefs.as_dict(),
        )
        self.playground = self.steady_panel.playground
        dl.addWidget(self.steady_panel)
        lay.addWidget(demo)

        config, cfg = card(spacing=8)
        cfg.addWidget(label('Assist settings', 'sectionTitle'))
        cfg.addWidget(label('Stabilization strength', 'cardTitle'))
        self.strength_slider, sr = self._slider(0, 200, 5, 'tremor_strength', '%', ('Light', 'Maximum'))
        cfg.addLayout(sr)
        cfg.addSpacing(8)
        cfg.addWidget(label('Simulated tremor intensity', 'cardTitle'))
        self.intensity_slider, ir = self._slider(0, 100, 5, 'tremor_intensity', '%', ('Mild', 'Intense'))
        cfg.addLayout(ir)
        cfg.addSpacing(8)
        cfg.addWidget(label('Click zone size', 'cardTitle'))
        self.target_slider, tr = self._slider(100, 200, 10, 'target_size_pct', '%', ('Normal', 'Large'))
        cfg.addLayout(tr)
        lay.addWidget(config)
        lay.addStretch()
        return page

    # ------------------------------------------------------------------ SmartInterface
    def _page_interface(self):
        page, lay = self._page(
            'SmartInterface',
            'Reading comfort for every Younify window.',
            icon_name='interface',
        )
        self.interface_toggle = self._bind_row(
            'module', 'smart_interface', 'Use SmartInterface on the healthcare form',
            'Simplify the sample appointment form.',
        )
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
        self.simple_row = self._bind_row(
            'option', 'reduce_complexity', 'Step-by-step layout',
            'Show the healthcare form one step at a time.', framed=False,
        )
        rl.addWidget(self.simple_row)
        lay.addWidget(reading)

        colours, cl = card(spacing=10)
        cl.addWidget(label('Colour theme', 'sectionTitle'))
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
        ht.addWidget(label('Soft wash to reduce glare. Pick a colour to turn it on.', 'bodyText', True))
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
        dt.addWidget(label('Apply these settings to a sample appointment form.', 'bandText', True))
        drow.addLayout(dt, 1)
        open_demo = button('Open demo', 'primaryButton')
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
            f'{names.get(self.prefs.tint_color, "Tint")} tint on at {self.prefs.tint_opacity}% (Younify only).'
            if active else 'Screen tint is off.'
        )

    # ------------------------------------------------------------------ appearance
    def _apply_visual_preferences(self) -> None:
        t = theme_mod.theme(self.prefs.color_profile)
        off = '#5B6B66' if self.prefs.color_profile == 'high_contrast' else '#A8B8C8'
        Switch.set_colors(t.active, off, '#FFFFFF', t.primary)
        self.setStyleSheet(theme_mod.stylesheet(self.prefs.font_size_pct, self.prefs.color_profile))
        theme_mod.apply_letter_spacing(self.prefs.letter_spacing_px)
        for tile in self._icon_tiles:
            tile.set_colors(t.mint, t.primary)
        for header in self._photo_headers:
            header.set_shade(t.sidebar)
        self._update_nav_icons()
        for key, sw in getattr(self, '_theme_buttons', {}).items():
            sw.setChecked(key == self.prefs.color_profile)
            sw.set_caption_color(t.heading)
        for sw in getattr(self, '_tint_buttons', {}).values():
            sw.set_caption_color(t.heading)
        if hasattr(self, 'steady_panel'):
            self.steady_panel.set_theme(t)
        for sw in self.findChildren(Switch):
            sw.update()
        self.tint_manager.update(color=self.prefs.tint_color, opacity=self.prefs.tint_opacity)

    def closeEvent(self, event):
        self.tint_manager.disable()
        super().closeEvent(event)

    # ------------------------------------------------------------------ navigation
    def _navigate(self, key):
        if hasattr(self, 'steady_panel') and self.steady_panel.trial_running and key != 'steady':
            self.steady_panel.abort_trial()
        self.stack.setCurrentWidget(self._pages[key])
        for k, btn in self._nav.items():
            btn.setChecked(k == key)
        splash = key == 'home'
        self.top_nav.setVisible(not splash)
        self.footer.setVisible(not splash)
        self.profile_button.setChecked(key == 'personalize')
        self._update_nav_icons()
        if splash:
            self._fade_in(self.home_logo, 700)
            self._splash_timer.start(SPLASH_MS)
        else:
            self._splash_timer.stop()

    def _update_nav_icons(self) -> None:
        t = theme_mod.theme(self.prefs.color_profile)
        for b, name in self._nav_icons:
            on = b.isCheckable() and b.isChecked()
            b.setIcon(icons.icon(name, t.on_primary if on else t.heading, 18))

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
        was_steady = self.prefs.steady_hand
        if profile_id != 'custom':
            self.prefs.profile = profile_id
            for key in MODULE_KEYS:
                setattr(self.prefs, key, bool(p[key]))
        else:
            self.prefs.profile = 'custom'
        self._sync_steady_strength(was_steady)
        self._apply_preferences_to_engine()
        self._save()
        self._refresh()

    def _sync_steady_strength(self, was_on: bool) -> None:
        """SteadyHand off: stabilization strength goes to 0. Back on: the previous strength returns."""
        on = bool(self.prefs.steady_hand)
        if was_on and not on:
            if self.prefs.tremor_strength > 0:
                self._strength_before_off = self.prefs.tremor_strength
            self.prefs.tremor_strength = 0
        elif on and not was_on and self.prefs.tremor_strength == 0:
            self.prefs.tremor_strength = getattr(self, '_strength_before_off', AccessibilitySettings().tremor_strength)

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
        was_steady = self.prefs.steady_hand
        setattr(self.prefs, key, bool(value))
        if key == 'steady_hand':
            self._sync_steady_strength(was_steady)
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
            f'SteadyHand {"on" if self.prefs.steady_hand else "off"} · '
            f'SmartInterface {"on" if self.prefs.smart_interface else "off"} · '
            f'Text {self.prefs.font_size_pct}% · {theme_name}'
        )
        cards = self.feature_cards
        running = bool(self.prefs.gaze_control)
        cards['gaze'].set_status('Running' if running else 'Ready', running)
        cards['gaze'].meta.hide()
        cards['steady'].set_status('On' if self.prefs.steady_hand else 'Off', self.prefs.steady_hand)
        cards['steady'].meta.setText(
            f'Strength {self.prefs.tremor_strength}% · Intensity {self.prefs.tremor_intensity} · '
            f'Zones {self.prefs.target_size_pct}%'
        )
        cards['interface'].set_status('On' if self.prefs.smart_interface else 'Off', self.prefs.smart_interface)
        cards['interface'].meta.setText(
            f'Text {self.prefs.font_size_pct}% · Spacing {self.prefs.letter_spacing_px} px · {theme_name}'
        )
        self.quick_font_value.setText(f'{self.prefs.font_size_pct} %')
        for kind, sw in self._quick_switches:
            value = {'contrast': self.prefs.color_profile == 'high_contrast',
                     'tint': self.tint_manager.active}[kind]
            sw.blockSignals(True)
            sw.setChecked(value)
            sw.blockSignals(False)
        for k, btn in self._preset_buttons.items():
            btn.setChecked(k == self.prefs.profile)
        for kind, key, row in self._bound_rows:
            row.set_value(self.tint_manager.active if kind == 'tint' else bool(getattr(self.prefs, key, False)))
        self.gaze_toggle.set_value(running)
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
