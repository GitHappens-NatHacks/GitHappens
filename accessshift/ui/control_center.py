"""AccessShift control center: preferences-first desktop UI for macOS and Windows.

This replaces the booking-centric window without touching the demo portal.  It
uses the existing AdaptiveEngine and SteadyHandController APIs.  Platform-side
hooks (camera worker, system pointer, browser extension) are integration tasks,
not capabilities claimed by the UI.
"""
from __future__ import annotations

import math
import time
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QColor, QCursor, QPainter, QPen
from PySide6.QtWidgets import (
    QApplication, QComboBox, QFrame, QGridLayout, QHBoxLayout, QLabel, QLineEdit, QMainWindow,
    QMessageBox, QPushButton, QScrollArea, QSlider, QStackedWidget,
    QVBoxLayout, QWidget,
)

from accessshift.engine.adaptive_engine import AdaptiveEngine
from accessshift.modules.smartinterface import (
    ScreenTintManager, VisualPreview, apply_accessshift_appearance,
)
from accessshift.modules.steadyhand.controller import SteadyHandController
from accessshift.ui.control_center_components import (
    PreferenceRow, StatCard, button, card, label,
)
from accessshift.ui.control_center_settings import (
    AccessibilitySettings, PROFILES, load_settings, save_settings,
)


class TremorPlayground(QWidget):
    """Mouse-only demo of in-app tremor smoothing; never moves the OS pointer."""
    metrics_changed = Signal(int, int)

    def __init__(self, controller: SteadyHandController):
        super().__init__()
        self.controller = controller
        self.setMinimumHeight(250)
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.setAccessibleName('Tremor accuracy practice area; click the purple target')
        self._inside = False
        self._mouse = (150.0, 130.0)
        self._raw = self._mouse
        self._stable = self._mouse
        self._hits = 0
        self._misses = 0
        self._simulated = True
        self.timer = QTimer(self)
        self.timer.setInterval(40)
        self.timer.timeout.connect(self._tick)
        self.timer.start()

    def set_simulation(self, enabled: bool) -> None:
        self._simulated = enabled
        self.update()

    def reset_scores(self) -> None:
        self._hits = self._misses = 0
        self.metrics_changed.emit(0, 0)
        self.update()

    def _target(self):
        return (max(90.0, self.width() * .76), max(75.0, self.height() * .51))

    def _tick(self) -> None:
        if not self.isVisible():
            return
        x, y = self._mouse
        if self._simulated:
            t = time.perf_counter()
            x += 9 * math.sin(t * 27) + 4 * math.sin(t * 39)
            y += 9 * math.cos(t * 30) + 4 * math.cos(t * 46)
        self._raw = (x, y)
        self._stable = self.controller.stabilize(x, y, time.perf_counter())
        self.update()

    def mouseMoveEvent(self, event):
        p = event.position()
        self._mouse = (p.x(), p.y())
        self._inside = True
        super().mouseMoveEvent(event)

    def leaveEvent(self, event):
        self._inside = False
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            tx, ty = self._target()
            x, y = self._stable
            hit = math.dist((x, y), (tx, ty)) <= 30
            if hit:
                self._hits += 1
            else:
                self._misses += 1
            self.metrics_changed.emit(self._hits, self._misses)
        super().mousePressEvent(event)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor('#F6F5FF'))
        p.drawRoundedRect(self.rect().adjusted(0, 0, -1, -1), 15, 15)
        p.setPen(QPen(QColor('#E9E4FF'), 1))
        for x in range(28, self.width(), 29):
            for y in range(28, self.height(), 29):
                p.drawPoint(x, y)
        tx, ty = self._target()
        p.setPen(QPen(QColor('#DED6FF'), 2))
        p.setBrush(QColor('#EEE9FF'))
        p.drawEllipse(int(tx - 38), int(ty - 38), 76, 76)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor('#674BE8'))
        p.drawEllipse(int(tx - 23), int(ty - 23), 46, 46)
        p.setPen(QColor('#FFFFFF'))
        p.drawText(int(tx - 12), int(ty + 5), 'CLICK')
        if self._inside:
            rx, ry = self._raw
            sx, sy = self._stable
            p.setPen(QPen(QColor('#FB8F7B'), 2))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(int(rx - 9), int(ry - 9), 18, 18)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor('#4934C7'))
            p.drawEllipse(int(sx - 6), int(sy - 6), 12, 12)
        p.setPen(QColor('#7B739A'))
        p.drawText(17, 24, 'PRACTICE  /  aim for the purple circle')
        p.drawText(17, self.height() - 14, 'Coral = raw pointer   •   Purple = stabilized pointer')
        p.end()


class HeadStartButton(QPushButton):
    """Big Start/Stop button for head movement control (keeps the toggle's set_value API)."""

    def __init__(self):
        super().__init__()
        self.setMinimumHeight(64)
        self.setStyleSheet('QPushButton { font-size: 18px; }')  # colours still come from the app theme
        self.set_value(False)

    def set_value(self, on: bool) -> None:
        self.setText('Stop head control' if on else 'Start head control')
        self.setObjectName('secondaryButton' if on else 'primaryButton')
        self.style().unpolish(self)
        self.style().polish(self)


class MainWindow(QMainWindow):
    """Drop-in replacement for accessshift.ui.main_window.MainWindow(repo_root)."""

    preferences_changed = Signal(object)  # dict; app services may subscribe
    calibration_requested = Signal()  # gaze team can connect worker/controller
    assistance_changed = Signal(bool)

    def __init__(self, repo_root: Path):
        super().__init__()
        self.repo_root = Path(repo_root)
        self.prefs = load_settings()
        self.engine = AdaptiveEngine(self)
        self.steady = SteadyHandController()
        self.speech = None  # instantiated only when the user presses Speak
        self._nav = {}
        self._pages = {}
        self._toggle_rows = {}
        self._sliders = {}
        self._preset_buttons = {}
        self._base_qss = Path(__file__).with_name('control_center_styles.qss').read_text(encoding='utf-8')
        self.tint_manager = ScreenTintManager(QApplication.instance())
        self._syncing_engine = True
        self._build_ui()
        self.tint_manager.register_window(self)  # Restrict tint to this application window
        self.engine.modules_changed.connect(self._on_external_modules_changed)
        self._apply_preferences_to_engine()
        self._syncing_engine = False
        self._refresh()
        self._navigate('overview' if self.prefs.initial_setup_complete else 'personalize')
        self.resize(1220, 810)
        self.setMinimumSize(940, 650)
        self.setWindowTitle('AccessShift AI  ·  Accessibility Settings')
        self._apply_visual_preferences()

    def _build_ui(self):
        root = QWidget()
        root.setObjectName('appRoot')
        self.setCentralWidget(root)
        outer = QHBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        side = QFrame()
        side.setObjectName('sidebar')
        side.setFixedWidth(246)
        side_l = QVBoxLayout(side)
        side_l.setContentsMargins(18, 28, 18, 20)
        side_l.setSpacing(5)
        brand = QHBoxLayout()
        mark = label('✦', 'logoMark')
        mark.setFixedSize(43, 43)
        mark.setAlignment(Qt.AlignmentFlag.AlignCenter)
        brand.addWidget(mark)
        text_l = QVBoxLayout()
        text_l.setSpacing(2)
        text_l.addWidget(label('AccessShift', 'brandName'))
        text_l.addWidget(label('ACCESSIBILITY ASSISTANT', 'brandSub'))
        brand.addLayout(text_l)
        side_l.addLayout(brand)
        side_l.addSpacing(24)
        nav_sections = [
            ('WORKSPACE', [('overview', '▦   Dashboard'), ('personalize', '◈   My accessibility profile')]),
            ('ACCESSIBILITY TOOLS', [
                ('gaze', '◎   Head movement control'),
                ('steady', '⌁   SteadyHand'),
                ('interface', '◐   SmartInterface'),
                ('speech', '◌   Communication'),
            ]),
            ('TRY IT OUT', [('test', '▣   Demo Lab & tests')]),
        ]
        for section, entries in nav_sections:
            side_l.addWidget(label(section, 'sideSection'))
            side_l.addSpacing(3)
            for key, text in entries:
                nav_button = button(text, 'navButton')
                nav_button.setCheckable(True)
                nav_button.setMinimumHeight(40)
                nav_button.clicked.connect(lambda _, k=key: self._navigate(k))
                nav_button.setAccessibleName(text.strip())
                side_l.addWidget(nav_button)
                self._nav[key] = nav_button
            side_l.addSpacing(10)
        side_l.addStretch()
        info, info_l = card(name='innerCard', margins=12, spacing=5)
        info_l.addWidget(label('●  PRIVATE BY DESIGN', 'goodPill'))
        info_l.addWidget(label('Your settings stay on this computer.', 'micro', True))
        side_l.addWidget(info)
        side_l.addSpacing(8)
        side_l.addWidget(label('GitHappens  ·  natHacks 2026', 'sidebarFoot'))
        outer.addWidget(side)

        right = QWidget()
        right_l = QVBoxLayout(right)
        right_l.setContentsMargins(0, 0, 0, 0)
        right_l.setSpacing(0)
        top_bar = QFrame()
        top_bar.setObjectName('topBar')
        top_l = QHBoxLayout(top_bar)
        top_l.setContentsMargins(33, 14, 33, 14)
        top_l.setSpacing(12)
        top_l.addWidget(label('ACCESSIBILITY WORKSPACE', 'topBarTitle'))
        top_l.addStretch()
        top_l.addWidget(label('●  LOCAL DEMO', 'topBarBadge'))
        self.top_bar_layout = top_l
        right_l.addWidget(top_bar)
        self.stack = QStackedWidget()
        right_l.addWidget(self.stack, 1)
        for key, method in [
            ('overview', self._page_overview),
            ('personalize', self._page_personalize),
            ('gaze', self._page_gaze),
            ('steady', self._page_steady),
            ('interface', self._page_interface),
            ('speech', self._page_communication),
            ('test', self._page_test),
        ]:
            page = method()
            self._pages[key] = page
            self.stack.addWidget(page)
        foot = QFrame()
        foot.setObjectName('footerBar')
        fl = QHBoxLayout(foot)
        fl.setContentsMargins(33, 11, 33, 11)
        fl.addWidget(label('AccessShift AI  ·  Local accessibility prototype', 'footerText'))
        fl.addStretch()
        self.footer_status = label('Preferences saved locally', 'footerText')
        fl.addWidget(self.footer_status)
        right_l.addWidget(foot)
        outer.addWidget(right, 1)

    def _page(self, eyebrow, title, subtitle):
        scroller = QScrollArea()
        scroller.setWidgetResizable(True)
        scroller.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        container = QWidget()
        container.setObjectName('scrollContent')
        content = QVBoxLayout(container)
        content.setContentsMargins(34, 29, 34, 38)
        content.setSpacing(18)
        content.addWidget(label(eyebrow, 'eyebrow'))
        content.addWidget(label(title, 'pageTitle'))
        desc = label(subtitle, 'pageDescription', True)
        content.addWidget(desc)
        content.addSpacing(5)
        scroller.setWidget(container)
        return scroller, content

    def _section(self, lay, title, subtitle=None):
        lay.addWidget(label(title, 'sectionTitle'))
        if subtitle:
            lay.addWidget(label(subtitle, 'bodyText', True))

    def _page_overview(self):
        page, lay = self._page('WELCOME TO ACCESS SHIFT', 'Accessibility, your way.',
                               'Configure your tools, preview your changes, and return whenever you need.')
        hero, hl = card(name='hero', margins=27, spacing=12)
        hl.addWidget(label('PERSONALIZED DIGITAL ACCESS', 'heroEyebrow'))
        hl.addWidget(label('Make every interaction easier.', 'heroTitle'))
        hl.addWidget(label('Fine-tune eye control, mouse stabilization, visual accessibility and communication in one place.',
                           'heroDescription', True))
        hr = QHBoxLayout()
        self.overview_profile = label('Your setup: Custom', 'heroBadge')
        hr.addWidget(self.overview_profile)
        hr.addStretch()
        edit = button('Customize profile  →', 'heroButton')
        edit.clicked.connect(lambda: self._navigate('personalize'))
        hr.addWidget(edit)
        hl.addLayout(hr)
        lay.addWidget(hero)
        row = QHBoxLayout()
        self.stat_modules = StatCard('SELECTED FEATURES', '0 / 4', 'Selected in your profile')
        self.stat_profile = StatCard('CURRENT PROFILE', 'Custom', 'Edit whenever you like')
        self.stat_platform = StatCard('DEMO ENVIRONMENT', 'Local only', 'macOS + Windows interface')
        for w in (self.stat_modules, self.stat_profile, self.stat_platform):
            row.addWidget(w, 1)
        lay.addLayout(row)
        self._section(lay, 'Your accessibility toolkit', 'Your chosen settings are saved automatically. Feature availability depends on module integration.')
        grid = QGridLayout()
        grid.setSpacing(13)
        self.overview_module_labels = {}
        for i, (key, title, desc) in enumerate([
            ('gaze_control', 'Head movement control', 'Webcam head pointing · ready to use'),
            ('steady_hand', 'SteadyHand', 'Mouse smoothing · in-app test ready'),
            ('smart_interface', 'SmartInterface', 'Visual adaptation in the healthcare demo'),
            ('predictive_speech', 'Communication', 'Text-to-speech · backend dependent'),
        ]):
            item, item_l = card(margins=18, spacing=7)
            title_row = QHBoxLayout()
            title_row.addWidget(label(title, 'cardTitle'))
            title_row.addStretch()
            pill = label('Off', 'pill')
            title_row.addWidget(pill)
            item_l.addLayout(title_row)
            item_l.addWidget(label(desc, 'bodyText', True))
            grid.addWidget(item, i // 2, i % 2)
            self.overview_module_labels[key] = pill
        lay.addLayout(grid)
        note, nl = card(name='innerCard', margins=15)
        nl.addWidget(label('Prototype status', 'cardTitle'))
        nl.addWidget(label('Your settings and local demos work inside AccessShift. Webcam navigation and OS-level pointer control '
                           'are separate team integrations. SmartInterface adapts only the bundled healthcare Demo Lab, '
                           'not third-party websites.', 'bodyText', True))
        lay.addWidget(note)
        lay.addStretch()
        return page

    def _page_personalize(self):
        page, lay = self._page('PERSONALIZATION', 'My accessibility profile',
                               'Start from a preset or choose a custom mix. These are preferences, not diagnoses.')
        self._section(lay, 'Start with a setup')
        grid = QGridLayout()
        grid.setSpacing(12)
        for i, (key, p) in enumerate(PROFILES.items()):
            name = p['label']
            description = p['description']
            btn = button(f'{name}\n\n{description}', 'presetButton')
            btn.setCheckable(True)
            btn.setMinimumHeight(91)
            btn.clicked.connect(lambda _, k=key: self._apply_profile(k))
            grid.addWidget(btn, i // 2, i % 2)
            self._preset_buttons[key] = btn
        lay.addLayout(grid)
        self._section(lay, 'Fine-tune your assistance')
        options = [
            ('gaze_control', 'Head movement navigation', 'Choose options by turning your head, using only your webcam.'),
            ('steady_hand', 'Stabilize my mouse', 'Smooth shaky cursor movements and help with small targets.'),
            ('smart_interface', 'SmartInterface demo', 'Enable the simpler layout in the bundled healthcare demo.'),
            ('predictive_speech', 'Communication support', 'Prepare text-to-speech and predictive text options.'),
        ]
        for key, name, desc in options:
            r = PreferenceRow(name, desc)
            r.changed.connect(lambda value, k=key: self._change_module(k, value))
            self._toggle_rows[key] = r
            lay.addWidget(r)
        actions = QHBoxLayout()
        actions.addStretch()
        done = button('Save profile & return to dashboard  →', 'primaryButton')
        done.clicked.connect(self._finish_setup)
        actions.addWidget(done)
        lay.addLayout(actions)
        lay.addStretch()
        return page

    # Head movement control: one Start button, three steps, a speed choice, an eyes note.
    HEAD_SPEEDS = (('relaxed', 'Relaxed', 1600), ('normal', 'Normal', 1100), ('quick', 'Quick', 800))

    def _page_gaze(self):
        page, lay = self._page('HANDS-FREE NAVIGATION', 'Head movement control',
                               'Choose options by turning your head. Only your webcam is needed.')
        self.gaze_notice = label('', 'warningPill', True)  # why hands-free stopped, if it did
        self.gaze_notice.setStyleSheet('font-size: 14px; padding: 12px 16px;')
        self.gaze_notice.hide()
        lay.addWidget(self.gaze_notice)
        start_box, sb = card(margins=24, spacing=10)
        self.gaze_toggle = HeadStartButton()
        self.gaze_toggle.clicked.connect(lambda: self._change_module('gaze_control', not self.prefs.gaze_control))
        sb.addWidget(self.gaze_toggle)
        sb.addWidget(label('Opens a full-screen view with large options. Setup takes about 10 seconds.',
                           'bodyText', True))
        lay.addWidget(start_box)

        steps, st = card(spacing=14)
        st.addWidget(label('How it works', 'sectionTitle'))
        for number, title, text in (
            ('1', 'Set up', 'Face the screen, then turn your head when the arrows ask.'),
            ('2', 'Choose', 'Turn your head toward an option. Hold still, or blink slowly, to choose it.'),
            ('3', 'Stop', 'Choose Exit, or close your eyes for 3 seconds.'),
        ):
            row = QHBoxLayout()
            row.setSpacing(14)
            row.addWidget(label(number, 'number'))
            text_col = QVBoxLayout()
            text_col.setSpacing(2)
            text_col.addWidget(label(title, 'cardTitle'))
            text_col.addWidget(label(text, 'bodyText', True))
            row.addLayout(text_col, 1)
            st.addLayout(row)
        lay.addWidget(steps)

        speed, sp = card(spacing=10)
        sp.addWidget(label('Selection speed', 'sectionTitle'))
        sp.addWidget(label('How long to hold still before an option is chosen.', 'bodyText', True))
        choices = QHBoxLayout()
        choices.setSpacing(12)
        self._dwell_buttons = {}
        for key, name, ms in self.HEAD_SPEEDS:
            b = button(f'{name}  ·  {ms / 1000:g} s', 'presetButton')
            b.setCheckable(True)
            b.setMinimumHeight(54)
            b.clicked.connect(lambda _=False, ms=ms: self._change_option('gaze_dwell_ms', ms))
            self._dwell_buttons[key] = b
            choices.addWidget(b)
        sp.addLayout(choices)
        lay.addWidget(speed)

        eyes, en = card(name='innerCard')
        en.addWidget(label('Prefer to use your eyes?', 'cardTitle'))
        en.addWidget(label('You can switch to eye movement at any time with the "Pointing with" button '
                           'in the full-screen view. Head movement is steadier on most laptop webcams.',
                           'bodyText', True))
        lay.addWidget(eyes)
        lay.addStretch()
        return page

    def _page_steady(self):
        page, lay = self._page('PRECISION INPUT', 'SteadyHand · Mouse assistance',
                               'Reduce pointer jitter and make small targets easier to select in supported experiences.')
        row = PreferenceRow('Enable SteadyHand', 'Use adaptive smoothing when the pointer integration is active.')
        row.changed.connect(lambda v: self._change_module('steady_hand', v))
        self.steady_toggle = row
        lay.addWidget(row)
        config, cfg = card()
        cfg.addWidget(label('Stabilization strength', 'sectionTitle'))
        cfg.addWidget(label('Higher values smooth more movement but may feel slower.', 'bodyText', True))
        self.strength_slider, sr = self._slider(0, 100, 5, 'tremor_strength', '%')
        cfg.addLayout(sr)
        cfg.addSpacing(5)
        cfg.addWidget(label('Clickable target size', 'cardTitle'))
        cfg.addWidget(label('Preference for supported overlays and adapted interfaces.', 'bodyText'))
        self.target_slider, tr = self._slider(100, 200, 10, 'target_size_pct', '%')
        cfg.addLayout(tr)
        lay.addWidget(config)
        test_btn = button('Open live in-app tremor test  →', 'primaryButton')
        test_btn.clicked.connect(lambda: self._navigate('test'))
        lay.addWidget(test_btn, alignment=Qt.AlignmentFlag.AlignLeft)
        info, il = card(name='innerCard')
        il.addWidget(label('About system-wide control', 'cardTitle'))
        il.addWidget(label('The current team controller supports in-app stabilization. '
                           'Moving the system pointer requires separate macOS/Windows adapters and permissions. '
                           'The settings here do not silently take over your OS cursor.', 'bodyText', True))
        lay.addWidget(info)
        lay.addStretch()
        return page

    def _page_interface(self):
        page, lay = self._page('VISUAL ACCESSIBILITY', 'SmartInterface',
                               'Personalize AccessShift and the live healthcare demo. No changes are made to other applications.')
        row = PreferenceRow('Enable SmartInterface in Demo Lab', 'Turn the bundled healthcare form into a simpler, more accessible interface.')
        row.changed.connect(lambda v: self._change_module('smart_interface', v))
        self.interface_toggle = row
        lay.addWidget(row)
        options, ol = card()
        ol.addWidget(label('Live appearance settings', 'sectionTitle'))
        self.simple_row = PreferenceRow('Guided, distraction-free layout', 'Reduce clutter and display the healthcare form in clear steps.')
        self.simple_row.changed.connect(lambda v: self._change_option('reduce_complexity', v))
        ol.addWidget(self.simple_row)
        ol.addWidget(label('Text size · AccessShift and Demo Lab', 'cardTitle'))
        self.font_slider, fr = self._slider(90, 160, 10, 'font_size_pct', '%')
        ol.addLayout(fr)
        ol.addWidget(label('Letter spacing · Demo Lab', 'cardTitle'))
        self.spacing_slider, spacing_row = self._slider(0, 4, 1, 'letter_spacing_px', 'px')
        ol.addLayout(spacing_row)
        ol.addWidget(label('Colour theme · both windows', 'cardTitle'))
        self.color_combo = QComboBox()
        for text, value in [
            ('Standard', 'standard'), ('High contrast', 'high_contrast'),
            ('Warm reading', 'warm'), ('Cool blue', 'cool'),
        ]:
            self.color_combo.addItem(text, value)
        self.color_combo.setAccessibleName('Colour theme')
        self.color_combo.currentIndexChanged.connect(
            lambda _: self._change_option('color_profile', self.color_combo.currentData()))
        ol.addWidget(self.color_combo)
        ol.addWidget(label('Live preview', 'cardTitle'))
        self.visual_preview = VisualPreview()
        ol.addWidget(self.visual_preview)
        ol.addWidget(label('Visual preferences update AccessShift immediately and the healthcare form while Demo Lab is open. '
                           'They do not alter system fonts or unrelated applications.', 'bodyText', True))
        lay.addWidget(options)

        tint, tl = card()
        tl.addWidget(label('Optional colour tint · local windows only', 'sectionTitle'))
        tl.addWidget(label('Add a subtle overlay to the AccessShift control center and its healthcare demo window. '
                           'The desktop, browser and all other applications remain untouched.', 'bodyText', True))
        self.tint_color_combo = QComboBox()
        for text, value in [
            ('Warm amber', 'warm'), ('Cool blue', 'cool'), ('Soft rose', 'rose'),
        ]:
            self.tint_color_combo.addItem(text, value)
        self.tint_color_combo.setAccessibleName('AccessShift window tint colour')
        self.tint_color_combo.currentIndexChanged.connect(
            lambda _: self._change_option('tint_color', self.tint_color_combo.currentData()))
        tl.addWidget(self.tint_color_combo)
        tl.addWidget(label('Tint intensity (0–20%)', 'cardTitle'))
        self.tint_slider, tint_row = self._slider(0, 20, 1, 'tint_opacity', '%')
        tl.addLayout(tint_row)
        self.tint_row = PreferenceRow('Tint only AccessShift windows',
                                      'Apply only to these two app-owned windows; no full-screen overlays.')
        self.tint_row.changed.connect(self._set_screen_tint)
        tl.addWidget(self.tint_row)
        self.tint_status = label('Window tint is off', 'bodyText')
        tl.addWidget(self.tint_status)
        lay.addWidget(tint)
        lay.addStretch()
        return page

    def _page_communication(self):
        page, lay = self._page('COMMUNICATION & AAC', 'Speech & text assistance',
                               'Write a message and speak it aloud. Predictive suggestions are connected by Avneet’s module.')
        speak, spl = card()
        spl.addWidget(label('Text-to-speech settings', 'sectionTitle'))
        self.speech_row = PreferenceRow('Enable communication support',
                                        'Allow supported speech and predictive-text functionality.')
        self.speech_row.changed.connect(lambda v: self._change_module('predictive_speech', v))
        spl.addWidget(self.speech_row)
        spl.addWidget(label('Speaking speed', 'cardTitle'))
        self.speech_slider, srl = self._slider(100, 220, 10, 'speech_rate', 'wpm')
        spl.addLayout(srl)
        spl.addWidget(label('Test message', 'cardTitle'))
        self.speech_input = QLineEdit('Hello, I am using AccessShift to communicate.')
        self.speech_input.setAccessibleName('Message to speak')
        spl.addWidget(self.speech_input)
        speak_button = button('Speak message  ▶', 'primaryButton')
        speak_button.clicked.connect(self._speak)
        spl.addWidget(speak_button, alignment=Qt.AlignmentFlag.AlignLeft)
        lay.addWidget(speak)
        info, il = card(name='innerCard')
        il.addWidget(label('Module ownership', 'cardTitle'))
        il.addWidget(label('Avneet owns the speech engine and predictive text. This page exposes the controls; '
                           'text-to-speech is available only if its Python backend is installed and working.',
                           'bodyText', True))
        lay.addWidget(info)
        lay.addStretch()
        return page

    def _set_screen_tint(self, enabled: bool) -> None:
        try:
            if enabled:
                self.tint_manager.update(color=self.prefs.tint_color, opacity=self.prefs.tint_opacity)
                self.tint_manager.enable()
            else:
                self.tint_manager.disable()
        except Exception as exc:
            self.tint_manager.disable()
            QMessageBox.warning(self, 'Window tint unavailable',
                                'The local window overlay could not be applied.\n\n' + str(exc))
        self.tint_row.set_value(self.tint_manager.active)
        self.tint_status.setText('Tint on · AccessShift and Demo Lab only.' if self.tint_manager.active
                                 else 'Window tint is off · other applications are unaffected.')

    def _apply_visual_preferences(self) -> None:
        apply_accessshift_appearance(self, self._base_qss, self.prefs.font_size_pct, self.prefs.color_profile)
        if hasattr(self, 'visual_preview'):
            self.visual_preview.set_preferences(self.prefs.font_size_pct, self.prefs.color_profile,
                                                self.prefs.letter_spacing_px)
        if hasattr(self, 'color_combo'):
            self.color_combo.blockSignals(True)
            self.color_combo.setCurrentIndex(max(0, self.color_combo.findData(self.prefs.color_profile)))
            self.color_combo.blockSignals(False)
        if hasattr(self, 'tint_color_combo'):
            self.tint_color_combo.blockSignals(True)
            self.tint_color_combo.setCurrentIndex(max(0, self.tint_color_combo.findData(self.prefs.tint_color)))
            self.tint_color_combo.blockSignals(False)
        self.tint_manager.update(color=self.prefs.tint_color, opacity=self.prefs.tint_opacity)
        if hasattr(self, 'tint_row'):
            self.tint_row.set_value(self.tint_manager.active)
        if hasattr(self, 'tint_status'):
            self.tint_status.setText('Tint on · AccessShift and Demo Lab only.' if self.tint_manager.active
                                     else 'Window tint is off · other applications are unaffected.')

    def closeEvent(self, event):
        self.tint_manager.disable()
        super().closeEvent(event)

    def _page_test(self):
        page, lay = self._page('INTERACTIVE PROTOTYPES', 'Demo Lab & tests',
                               'Preview SmartInterface on a fictional healthcare form and explore SteadyHand in-app.')
        test, tl = card()
        tl.addWidget(label('SteadyHand • accuracy playground', 'sectionTitle'))
        tl.addWidget(label('Move the cursor into the area and click the purple target. '
                           'Compare the raw (coral) and smoothed (purple) indicators.', 'bodyText', True))
        self.playground = TremorPlayground(self.steady)
        tl.addWidget(self.playground)
        bars = QHBoxLayout()
        self.test_score = label('Hits: 0  •  Misses: 0  •  Accuracy: n/a', 'cardTitle')
        bars.addWidget(self.test_score)
        bars.addStretch()
        reset = button('Reset test', 'secondaryButton')
        reset.clicked.connect(self.playground.reset_scores)
        bars.addWidget(reset)
        tl.addLayout(bars)
        self.playground.metrics_changed.connect(self._update_test_score)
        self.simulation_row = PreferenceRow('Simulate shaky movement', 'Adds repeatable artificial jitter inside the test only.')
        self.simulation_row.set_value(True)
        self.simulation_row.changed.connect(self.playground.set_simulation)
        tl.addWidget(self.simulation_row)
        lay.addWidget(test)
        info, il = card(name='innerCard')
        il.addWidget(label('Current demo scope', 'cardTitle'))
        il.addWidget(label('This is a controlled software prototype, not a clinical assessment. '
                           'The SmartInterface demo is local-only. Head movement control runs locally with '
                           'your webcam. OS-level pointer control depends on teammates’ integrations.', 'bodyText', True))
        lay.addWidget(info)
        lay.addStretch()
        return page

    def _slider(self, minimum, maximum, step, key, suffix):
        widget = QSlider(Qt.Orientation.Horizontal)
        widget.setRange(minimum, maximum)
        widget.setSingleStep(step)
        widget.setPageStep(step)
        widget.setAccessibleName(key.replace('_', ' '))
        widget.valueChanged.connect(lambda value, k=key: self._change_option(k, value))
        value_label = label('', 'pill')
        row = QHBoxLayout()
        row.addWidget(widget, 1)
        row.addWidget(value_label)
        self._sliders[key] = (widget, value_label, suffix)
        return widget, row

    def _navigate(self, key):
        self.stack.setCurrentWidget(self._pages[key])
        for k, btn in self._nav.items():
            btn.setChecked(k == key)

    def _finish_setup(self):
        self.prefs.initial_setup_complete = True
        self._save()
        self._navigate('overview')

    def _apply_profile(self, profile_id):
        p = PROFILES[profile_id]
        if profile_id != 'custom':
            self.prefs.profile = profile_id
            for key in ('gaze_control', 'steady_hand', 'smart_interface', 'predictive_speech'):
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
            for key in ('gaze_control', 'steady_hand', 'smart_interface', 'predictive_speech'):
                self.engine.set_module(key, getattr(self.prefs, key))
        finally:
            self._syncing_engine = previous
        self.steady.strength = self.prefs.tremor_strength / 100.0
        self.steady.enabled = self.prefs.steady_hand and self.prefs.assistance_enabled

    def _on_external_modules_changed(self, flags):
        """Follow updates sent by other team members through AdaptiveEngine."""
        if self._syncing_engine:
            return
        self.prefs.profile = self.engine.profile.id
        for key in ('gaze_control', 'steady_hand', 'smart_interface', 'predictive_speech'):
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
        self._save()
        self._refresh()

    def _save(self):
        save_settings(self.prefs)
        self.preferences_changed.emit(self.prefs.as_dict())

    def _refresh(self):
        flags = ('gaze_control', 'steady_hand', 'smart_interface', 'predictive_speech')
        active = sum(bool(getattr(self.prefs, k)) for k in flags)
        name = PROFILES.get(self.prefs.profile, PROFILES['custom'])['label']
        self.overview_profile.setText('Your setup: ' + name)
        self.stat_modules.value.setText(f'{active} / 4')
        self.stat_profile.value.setText('Personal' if self.prefs.profile == 'custom' else 'Preset')
        for k, lbl in self.overview_module_labels.items():
            enabled = getattr(self.prefs, k)
            lbl.setText('Selected' if enabled else 'Off')
            lbl.setObjectName('goodPill' if enabled else 'pill')
            lbl.style().unpolish(lbl)
            lbl.style().polish(lbl)
        for k, btn in self._preset_buttons.items():
            btn.setChecked(k == self.prefs.profile)
        for k, row in self._toggle_rows.items():
            row.set_value(getattr(self.prefs, k))
        self.gaze_toggle.set_value(self.prefs.gaze_control)
        self.steady_toggle.set_value(self.prefs.steady_hand)
        self.interface_toggle.set_value(self.prefs.smart_interface)
        self.speech_row.set_value(self.prefs.predictive_speech)
        self.simple_row.set_value(self.prefs.reduce_complexity)
        for key, _name, ms in self.HEAD_SPEEDS:
            self._dwell_buttons[key].setChecked(self.prefs.gaze_dwell_ms == ms)
        for k, (slider, text, suffix) in self._sliders.items():
            value = int(getattr(self.prefs, k))
            slider.blockSignals(True)
            slider.setValue(value)
            slider.blockSignals(False)
            text.setText(f'{value} {suffix}')
        self.footer_status.setText('✓  Settings saved on this device')
        self._apply_visual_preferences()

    def _request_calibration(self):
        self.calibration_requested.emit()
        QMessageBox.information(
            self, 'Gaze calibration integration',
            'The calibration screen is not connected to the webcam worker yet.\n\n'
            'Your teammate can connect a handler to MainWindow.calibration_requested '
            'and then display the live calibration widget.',
        )

    def _speak(self):
        msg = self.speech_input.text().strip()
        if not msg:
            QMessageBox.information(self, 'Speech', 'Enter a phrase to speak first.')
            return
        if not self.prefs.predictive_speech:
            QMessageBox.information(self, 'Speech', 'Enable communication support first.')
            return
        try:
            if self.speech is None:
                from accessshift.modules.speech.tts import SpeechEngine
                self.speech = SpeechEngine()
            if not self.speech.enabled:
                raise RuntimeError('The speech engine could not initialize on this device.')
            if callable(getattr(self.speech, 'set_rate', None)):
                self.speech.set_rate(self.prefs.speech_rate)
            elif getattr(self.speech, '_engine', None) is not None:
                self.speech._engine.setProperty('rate', self.prefs.speech_rate)
            self.speech.speak(msg)
        except Exception as exc:
            QMessageBox.warning(self, 'Speech unavailable', str(exc))

    def _update_test_score(self, hits, misses):
        n = hits + misses
        accuracy = f'{hits / n:.0%}' if n else 'n/a'
        self.test_score.setText(f'Hits: {hits}  •  Misses: {misses}  •  Accuracy: {accuracy}')
