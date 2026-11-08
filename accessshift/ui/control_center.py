"""AccessShift control center: preferences-first desktop UI for macOS and Windows.

This replaces the booking-centric window without touching the demo portal.  It
uses the existing AdaptiveEngine and SteadyHandController APIs.  Platform-side
hooks (camera worker, system pointer, browser extension) are integration tasks,
not capabilities claimed by the UI.
"""
from __future__ import annotations

import time
from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QCursor, QPainter, QPen
from PySide6.QtWidgets import (
    QApplication, QComboBox, QFileDialog, QFrame, QGridLayout, QHBoxLayout, QLabel, QLineEdit, QMainWindow,
    QMessageBox, QPushButton, QScrollArea, QSlider, QStackedWidget,
    QVBoxLayout, QWidget,
)

from accessshift.engine.adaptive_engine import AdaptiveEngine
from accessshift.modules.smartinterface import (
    ScreenTintManager, VisualPreview, apply_accessshift_appearance,
)
from accessshift.modules.steadyhand.controller import SteadyHandController
from accessshift.modules.steadyhand.metrics import Trial, save_results
from accessshift.modules.steadyhand.targets import Target, TargetManager
from accessshift.ui.control_center_components import (
    PreferenceRow, StatCard, button, card, label,
)
from accessshift.ui.control_center_settings import (
    AccessibilitySettings, PROFILES, load_settings, save_settings,
)

SEQUENCE = ('doctor', 'date', 'time', 'review', 'book') * 2
LABELS = {
    'doctor': '1. Doctor',
    'date': '2. Date',
    'time': '3. Time',
    'review': '4. Review',
    'book': '5. Book',
}


class TremorPlayground(QWidget):
    """In-app tremor smoothing and target assistance evaluation canvas.

    Supports baseline, smoothing, target assistance, and combined modes with
    healthcare workflow targets, live accuracy metrics, and JSON trial export.
    """
    metrics_changed = Signal(int, int)
    trial_progress = Signal(object, object)
    trial_completed = Signal(object)

    MODES = [
        'Baseline (Raw input)',
        'SteadyHand smoothing',
        'Target assistance',
        'Smoothing + Target assistance',
    ]

    def __init__(self, controller: SteadyHandController, target_padding: float = 16.0):
        super().__init__()
        self.controller = controller
        self.setMinimumHeight(300)
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.setAccessibleName('SteadyHand accuracy practice and evaluation canvas')

        self.target_manager = TargetManager(padding=target_padding)
        self._mode_index = 3
        self.use_filter = True
        self.assisted = True

        self._inside = False
        self._mouse = (150.0, 130.0)
        self._raw = self._mouse
        self._stable = self._mouse
        self._hits = 0
        self._misses = 0
        self._simulated = True
        self._sim_start = time.perf_counter()

        self.trial: Trial | None = None
        self.results: list[Trial] = []

        self.timer = QTimer(self)
        self.timer.setInterval(30)
        self.timer.timeout.connect(self._tick)
        self.timer.start()
        self._rebuild_targets()

    def set_target_padding(self, padding: float) -> None:
        self.target_manager.padding = max(0.0, float(padding))
        self.update()

    def set_mode(self, mode_index: int) -> None:
        self._mode_index = max(0, min(len(self.MODES) - 1, mode_index))
        self.use_filter = self._mode_index in (1, 3)
        self.assisted = self._mode_index in (2, 3)
        self.controller.enabled = self.use_filter
        self.controller.reset()
        self.update()

    def start_trial(self) -> None:
        self.set_mode(self._mode_index)
        self.trial = Trial(self.MODES[self._mode_index], SEQUENCE)
        self.controller.reset()
        self._sim_start = time.perf_counter()
        self.update()
        self.trial_progress.emit(self.trial.summary(), self.trial.expected)

    def abort_trial(self) -> None:
        if self.trial and not self.trial.complete:
            self.trial = None
            self.update()

    def set_simulation(self, enabled: bool) -> None:
        self._simulated = enabled
        self._sim_start = time.perf_counter()
        self.controller.simulate_tremor = False
        self.update()

    def reset_scores(self) -> None:
        self._hits = 0
        self._misses = 0
        self.metrics_changed.emit(0, 0)
        self.update()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._rebuild_targets()

    def _rebuild_targets(self) -> None:
        w = max(400, self.width())
        h = max(200, self.height())
        btn_w = max(80.0, min(120.0, (w - 70) / 5.0 - 10.0))
        btn_h = max(36.0, min(48.0, h * 0.16))
        margin = 35.0
        avail_w = w - 2 * margin
        step_x = (avail_w - btn_w) / 4.0 if avail_w > btn_w else 90.0
        base_y = h * 0.46
        targets = []
        for i, key in enumerate(('doctor', 'date', 'time', 'review', 'book')):
            x = margin + i * step_x
            y = base_y + ((-1) ** i) * (btn_h * 0.42)
            targets.append(Target(key, LABELS[key], x, y, btn_w, btn_h))
        self.target_manager.set_targets(targets)

    def _tick(self) -> None:
        if not self.isVisible():
            return
        x, y = self._mouse
        now = time.perf_counter()
        if self._simulated:
            dx, dy = self.controller.tremor_offset(now - self._sim_start)
            x += dx
            y += dy
        self._raw = (x, y)
        self._stable = self.controller.stabilize(x, y, now) if self.use_filter else (x, y)
        self.update()

    def mouseMoveEvent(self, event) -> None:
        p = event.position()
        self._mouse = (p.x(), p.y())
        self._inside = True
        super().mouseMoveEvent(event)

    def leaveEvent(self, event) -> None:
        self._inside = False
        super().leaveEvent(event)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            sx, sy = self._stable
            target = self.target_manager.select(sx, sy, assisted=self.assisted)
            if self.trial and not self.trial.complete:
                hit = self.trial.record(target.id if target else None, sx, sy)
                if hit:
                    self._hits += 1
                else:
                    self._misses += 1
                self.metrics_changed.emit(self._hits, self._misses)
                self.trial_progress.emit(self.trial.summary(), self.trial.expected)
                if self.trial.complete:
                    self.results.append(self.trial)
                    self.trial_completed.emit(self.trial)
            else:
                if target is not None:
                    self._hits += 1
                else:
                    self._misses += 1
                self.metrics_changed.emit(self._hits, self._misses)
        super().mousePressEvent(event)

    def hideEvent(self, event) -> None:
        self.timer.stop()
        super().hideEvent(event)

    def showEvent(self, event) -> None:
        if not self.timer.isActive():
            self.timer.start()
        super().showEvent(event)

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor('#F6F5FF'))
        p.drawRoundedRect(self.rect().adjusted(0, 0, -1, -1), 14, 14)
        p.setPen(QPen(QColor('#E8E3FA'), 1))
        for gx in range(25, self.width(), 30):
            for gy in range(25, self.height(), 30):
                p.drawPoint(gx, gy)

        expected_id = self.trial.expected if (self.trial and not self.trial.complete) else None
        sx, sy = self._stable
        candidate = self.target_manager.select(sx, sy, assisted=self.assisted) if self._inside else None
        pad = self.target_manager.padding

        for t in self.target_manager.targets:
            rect = QRectF(t.x, t.y, t.width, t.height)
            if self.assisted and pad > 0:
                p.setPen(QPen(QColor('#B9ACF7'), 1, Qt.PenStyle.DashLine))
                p.setBrush(QColor('#ECE7FF'))
                p.drawRoundedRect(rect.adjusted(-pad, -pad, pad, pad), 9, 9)
            is_expected = t.id == expected_id
            if is_expected:
                p.setPen(QPen(QColor('#10B981'), 2))
                p.setBrush(QColor('#E6F9F0'))
            else:
                p.setPen(QPen(QColor('#C8C0EE'), 1))
                p.setBrush(QColor('#FFFFFF'))
            p.drawRoundedRect(rect, 7, 7)
            p.setPen(QColor('#065F46' if is_expected else '#312E5B'))
            font = p.font()
            font.setBold(is_expected)
            font.setPointSize(10)
            p.setFont(font)
            p.drawText(rect, Qt.AlignmentFlag.AlignCenter, t.label)
            if candidate and candidate.id == t.id:
                p.setPen(QPen(QColor('#F59E0B'), 2))
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.drawRoundedRect(rect.adjusted(-3, -3, 3, 3), 9, 9)

        if self._inside:
            rx, ry = self._raw
            if self._simulated or self.use_filter:
                p.setPen(QPen(QColor('#FB8F7B'), 2))
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.drawEllipse(QPointF(rx, ry), 9, 9)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor('#674BE8'))
            p.drawEllipse(QPointF(sx, sy), 5, 5)

        p.setPen(QColor('#6B648C'))
        font = p.font()
        font.setPointSize(9)
        font.setBold(False)
        p.setFont(font)
        status_text = f'EVALUATION PLAYGROUND  •  Mode: {self.MODES[self._mode_index]}'
        if self.trial and not self.trial.complete:
            status_text += f'  •  Target {self.trial.index + 1}/10: {LABELS.get(self.trial.expected, "")}'
        p.drawText(16, 22, status_text)
        p.drawText(
            16,
            self.height() - 12,
            'Coral ring = Raw pointer with tremor   •   Purple dot = Stabilized / assisted pointer   •   Gold outline = Selected candidate',
        )
        p.end()


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
        self.sidebar = side
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
                ('gaze', '◎   Eye & blink control'),
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
        self.workspace = right
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
            ('gaze_control', 'Eye & blink control', 'Head or eye pointing · webcam ready'),
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
            ('gaze_control', 'Eye & blink navigation', 'Navigate through webcam gaze and deliberate blink selection.'),
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

    def _page_gaze(self):
        page, lay = self._page(
            'HANDS-FREE NAVIGATION',
            'Eye & blink control',
            'Turn on head or eye pointing, then calibrate with the webcam. Default pointing source is head.',
        )
        row = PreferenceRow('Use eye / head navigation', 'Start webcam pointing and open the hands-free booking focus layout.')
        row.changed.connect(lambda v: self._change_module('gaze_control', v))
        self.gaze_toggle = row
        lay.addWidget(row)
        gaze_box, gb = card()
        gb.addWidget(label('How should selection work?', 'sectionTitle'))
        self.blink_row = PreferenceRow('Blink to select', 'Use a deliberate blink as confirmation after dwell has started.')
        self.blink_row.changed.connect(lambda v: self._change_option('blink_select', v))
        gb.addWidget(self.blink_row)
        gb.addWidget(label('Dwell time', 'cardTitle'))
        gb.addWidget(label('How long to look at a target before it becomes selected.', 'bodyText'))
        self.dwell_slider, dwell_row = self._slider(2800, 4200, 100, 'gaze_dwell_ms', 'ms')
        gb.addLayout(dwell_row)
        lay.addWidget(gaze_box)
        cal, cl = card(name='innerCard')
        cl.addWidget(label('Camera calibration', 'sectionTitle'))
        cl.addWidget(label(
            'Enable navigation above, then calibrate. Head mode shows guided poses; eyes mode uses on-screen dots.',
            'bodyText',
            True,
        ))
        cal_btn = button('Open gaze calibration', 'primaryButton')
        cal_btn.clicked.connect(self._request_calibration)
        cl.addWidget(cal_btn, alignment=Qt.AlignmentFlag.AlignLeft)
        lay.addWidget(cal)
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
        page, lay = self._page(
            'INTERACTIVE PROTOTYPES',
            'Demo Lab & tests',
            'Preview SmartInterface on a fictional healthcare form and run SteadyHand accuracy trials.',
        )
        test, tl = card()
        tl.addWidget(label('SteadyHand • accuracy & benchmark suite', 'sectionTitle'))
        tl.addWidget(label(
            'Select a test mode and run a 10-step simulated healthcare booking trial. '
            'Compare raw movement against One-Euro smoothing and target expansion.',
            'bodyText',
            True,
        ))

        ctrl_row = QHBoxLayout()
        self.test_mode_combo = QComboBox()
        for mode in TremorPlayground.MODES:
            self.test_mode_combo.addItem(mode)
        self.test_mode_combo.setCurrentIndex(3)
        self.test_mode_combo.currentIndexChanged.connect(self._on_test_mode_changed)
        ctrl_row.addWidget(self.test_mode_combo, 2)

        self.btn_start_trial = button('Start trial', 'primaryButton')
        self.btn_start_trial.clicked.connect(self._start_trial)
        ctrl_row.addWidget(self.btn_start_trial)

        self.btn_abort_trial = button('Abort trial', 'secondaryButton')
        self.btn_abort_trial.setEnabled(False)
        self.btn_abort_trial.clicked.connect(self._abort_trial)
        ctrl_row.addWidget(self.btn_abort_trial)

        self.btn_export_results = button('Export JSON', 'secondaryButton')
        self.btn_export_results.clicked.connect(self._export_trial_results)
        ctrl_row.addWidget(self.btn_export_results)

        reset = button('Reset scores', 'secondaryButton')
        reset.clicked.connect(self._reset_test_scores)
        ctrl_row.addWidget(reset)
        tl.addLayout(ctrl_row)

        self.playground = TremorPlayground(
            self.steady,
            target_padding=16.0 * (self.prefs.target_size_pct / 100.0),
        )
        tl.addWidget(self.playground)
        self.test_score = label(
            'Mode: Smoothing + Target assistance  •  Status: Ready for trial',
            'cardTitle',
        )
        tl.addWidget(self.test_score)
        self.playground.metrics_changed.connect(self._update_test_score)
        self.playground.trial_progress.connect(self._on_trial_progress)
        self.playground.trial_completed.connect(self._on_trial_completed)

        self.simulation_row = PreferenceRow(
            'Simulate shaky movement',
            'Applies multi-frequency tremor inside this test only.',
        )
        self.simulation_row.set_value(True)
        self.simulation_row.changed.connect(self.playground.set_simulation)
        tl.addWidget(self.simulation_row)
        lay.addWidget(test)

        hist_card, hl = card()
        hl.addWidget(label('Completed Trial Benchmarks', 'sectionTitle'))
        self.trial_history_label = label(
            'No completed trials yet. Choose a mode and click Start trial to benchmark accuracy.',
            'bodyText',
            True,
        )
        hl.addWidget(self.trial_history_label)
        lay.addWidget(hist_card)

        info, il = card(name='innerCard')
        il.addWidget(label('Evaluation protocol', 'cardTitle'))
        il.addWidget(label(
            'Each trial walks a 10-step sequence (Doctor → Date → Time → Review → Book × 2). '
            'Metrics record click latency, hits, misses, and accuracy for judging verification.',
            'bodyText',
            True,
        ))
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
        if hasattr(self, 'playground') and self.playground.trial and not self.playground.trial.complete and key != 'test':
            self.playground.abort_trial()
            self._abort_trial()
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
        if key == 'target_size_pct' and hasattr(self, 'playground'):
            self.playground.set_target_padding(16.0 * (self.prefs.target_size_pct / 100.0))
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
        self.blink_row.set_value(self.prefs.blink_select)
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

    def _on_test_mode_changed(self, index: int) -> None:
        self.playground.set_mode(index)
        self.test_score.setText(f'Mode: {self.playground.MODES[index]}  •  Status: Ready for trial')

    def _start_trial(self) -> None:
        self.playground.start_trial()
        self.test_mode_combo.setEnabled(False)
        self.btn_start_trial.setEnabled(False)
        self.btn_abort_trial.setEnabled(True)

    def _abort_trial(self) -> None:
        self.playground.abort_trial()
        self.test_mode_combo.setEnabled(True)
        self.btn_start_trial.setEnabled(True)
        self.btn_abort_trial.setEnabled(False)
        self.test_score.setText('Trial aborted. Ready to start again.')

    def _reset_test_scores(self) -> None:
        self.playground.reset_scores()
        self.test_score.setText('Scores reset.')

    def _on_trial_progress(self, summary: dict, expected: str | None) -> None:
        if expected is None:
            return
        lbl = LABELS.get(expected, expected)
        hits = summary['hits']
        misses = summary['misses']
        total = summary['interactions']
        acc = f"{summary['accuracy']:.0%}" if total > 0 else '—'
        elapsed = f"{summary['seconds']:.1f}s"
        self.test_score.setText(
            f'Target {hits + 1}/10: [{lbl}]  •  Hits: {hits}  •  Misses: {misses}  •  Accuracy: {acc}  •  Time: {elapsed}'
        )

    def _on_trial_completed(self, trial: Trial) -> None:
        self.test_mode_combo.setEnabled(True)
        self.btn_start_trial.setEnabled(True)
        self.btn_abort_trial.setEnabled(False)
        s = trial.summary()
        self.test_score.setText(
            f"Trial completed. Mode: {trial.mode}  •  Accuracy: {s['accuracy']:.0%}  •  Time: {s['seconds']:.1f}s"
        )
        self._refresh_trial_history()

    def _refresh_trial_history(self) -> None:
        if not self.playground.results:
            self.trial_history_label.setText('No completed trials yet.')
            return
        lines = []
        for i, t in enumerate(self.playground.results, 1):
            s = t.summary()
            lines.append(
                f"Trial #{i}  •  {s['mode']}: {s['accuracy']:.0%} accuracy  |  "
                f"{s['hits']} hits, {s['misses']} misses  |  {s['seconds']:.1f}s"
            )
        self.trial_history_label.setText('\n'.join(lines))

    def _export_trial_results(self) -> None:
        if not self.playground.results:
            QMessageBox.information(
                self,
                'Export Results',
                'No completed trials to export yet. Run at least one trial first.',
            )
            return
        default_name = f'steadyhand-results-{int(time.time())}.json'
        default_path = str(self.repo_root / default_name)
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            'Export Trial Results JSON',
            default_path,
            'JSON Files (*.json)',
        )
        if file_path:
            save_results(file_path, self.playground.results, extra=self.prefs.as_dict())
            QMessageBox.information(
                self,
                'Export Successful',
                f'Exported {len(self.playground.results)} trial records to:\n{file_path}',
            )

    def _update_test_score(self, hits, misses):
        n = hits + misses
        accuracy = f'{hits / n:.0%}' if n else '—'
        if not (self.playground.trial and not self.playground.trial.complete):
            self.test_score.setText(
                f'Free practice  •  Hits: {hits}  •  Misses: {misses}  •  Accuracy: {accuracy}'
            )
