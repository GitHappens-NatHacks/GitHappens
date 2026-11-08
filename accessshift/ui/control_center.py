"""AccessShift Focus UI 2.0 — uncluttered desktop accessibility preferences.

One top-level row of navigation, one source of settings, and a local demo.
Compatibility: MainWindow(repo_root), preferences_changed, calibration_requested,
assistance_changed, set_demo_launcher, _navigate, engine, steady and prefs.
"""
from __future__ import annotations

import json
import math
import sys
import time
from pathlib import Path

from PySide6.QtCore import Qt, QProcess, QTimer, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (
    QApplication, QComboBox, QFrame, QHBoxLayout, QLabel, QLineEdit,
    QMainWindow, QMessageBox, QPushButton, QScrollArea, QSlider,
    QStackedWidget, QVBoxLayout, QWidget,
)

from accessshift.engine.adaptive_engine import AdaptiveEngine
from accessshift.modules.smartinterface import (
    ScreenTintManager, VisualPreview, apply_accessshift_appearance,
)
from accessshift.modules.steadyhand.controller import SteadyHandController
from accessshift.ui.control_center_components import Switch, PreferenceRow
from accessshift.ui.control_center_settings import PROFILES, load_settings, save_settings

UI_VERSION = 'FOCUS-2.0.0'

FEATURES = (
    ('smart_interface', 'Visual clarity', 'Larger text and simpler local forms.', '01'),
    ('steady_hand', 'SteadyHand', 'Reduce unwanted mouse movement.', '02'),
    ('gaze_control', 'Eye & blink', 'Configure hands-free navigation.', '03'),
    ('predictive_speech', 'Communication', 'Speak a typed message aloud.', '04'),
)
DETAILS = (
    ('appearance', 'Display'), ('mouse', 'Pointer'),
    ('eyes', 'Gaze'), ('voice', 'Voice'),
)


def txt(message: str, kind: str = 'body', *, wrap: bool = False) -> QLabel:
    widget = QLabel(message)
    widget.setObjectName(kind)
    widget.setWordWrap(wrap)
    widget.setMinimumWidth(0)
    return widget


def btn(message: str, kind: str = 'secondaryButton') -> QPushButton:
    widget = QPushButton(message)
    widget.setObjectName(kind)
    widget.setMinimumHeight(44)
    widget.setCursor(Qt.CursorShape.PointingHandCursor)
    return widget


def surface(kind='surface', margin=24, gap=12):
    frame = QFrame()
    frame.setObjectName(kind)
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(margin, margin, margin, margin)
    layout.setSpacing(gap)
    return frame, layout


class ToolLine(QFrame):
    """One accessible feature toggle. No duplicate feature switch elsewhere."""
    changed = Signal(bool)

    def __init__(self, number: str, name: str, detail: str):
        super().__init__()
        self.setObjectName('toolLine')
        h = QHBoxLayout(self)
        h.setContentsMargins(16, 9, 16, 9)
        h.setSpacing(15)
        number_label = txt(number, 'toolNumber')
        number_label.setFixedSize(38, 38)
        number_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        h.addWidget(number_label)
        words = QVBoxLayout()
        words.setSpacing(3)
        words.addWidget(txt(name, 'toolTitle', wrap=True))
        words.addWidget(txt(detail, 'toolDetail', wrap=True))
        h.addLayout(words, 1)
        self.switch = Switch(name)
        self.switch.setAccessibleDescription(detail)
        self.switch.toggled.connect(self.changed.emit)
        h.addWidget(self.switch, alignment=Qt.AlignmentFlag.AlignVCenter)
        self.setMinimumHeight(70)

    def set_value(self, value: bool):
        self.switch.blockSignals(True)
        self.switch.setChecked(bool(value))
        self.switch.blockSignals(False)


class TremorPlayground(QWidget):
    """In-app test only: simulated jitter and filter readout, no OS mouse hooks."""
    metrics_changed = Signal(int, int)

    def __init__(self, controller):
        super().__init__()
        self.controller = controller
        self.setMinimumHeight(225)
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.setAccessibleName('Tremor practice: move the mouse and click the target')
        self._inside = False
        self._mouse = (150., 130.)
        self._raw = self._mouse
        self._stable = self._mouse
        self._hits = 0
        self._misses = 0
        self._simulated = True
        self.timer = QTimer(self)
        self.timer.setInterval(40)
        self.timer.timeout.connect(self._tick)
        self.timer.start()

    def set_simulation(self, enabled: bool):
        self._simulated = enabled
        self.update()

    def reset_scores(self):
        self._hits = self._misses = 0
        self.metrics_changed.emit(0, 0)
        self.update()

    def _target(self):
        return max(90., self.width() * .73), max(75., self.height() * .51)

    def _tick(self):
        if not self.isVisible():
            return
        x, y = self._mouse
        if self._simulated:
            t = time.perf_counter()
            x += 9 * math.sin(t * 27) + 4 * math.sin(t * 39)
            y += 9 * math.cos(t * 30) + 4 * math.cos(t * 46)
        self._raw = x, y
        self._stable = self.controller.stabilize(x, y, time.perf_counter())
        self.update()

    def mouseMoveEvent(self, event):
        p = event.position()
        self._mouse = p.x(), p.y()
        self._inside = True
        super().mouseMoveEvent(event)

    def leaveEvent(self, event):
        self._inside = False
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            hit = math.dist(self._stable, self._target()) <= 30
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
        p.setBrush(QColor('#F6F7FC'))
        p.drawRoundedRect(self.rect().adjusted(1, 1, -1, -1), 16, 16)
        p.setPen(QPen(QColor('#E6E8F0'), 1))
        for x in range(28, self.width(), 30):
            for y in range(28, self.height(), 30):
                p.drawPoint(x, y)
        tx, ty = self._target()
        p.setPen(QPen(QColor('#CEC9FE'), 2))
        p.setBrush(QColor('#EBE8FF'))
        p.drawEllipse(int(tx - 39), int(ty - 39), 78, 78)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor('#6455D8'))
        p.drawEllipse(int(tx - 24), int(ty - 24), 48, 48)
        p.setPen(QColor('white'))
        p.drawText(int(tx - 15), int(ty + 5), 'CLICK')
        if self._inside:
            rx, ry = self._raw
            sx, sy = self._stable
            p.setPen(QPen(QColor('#FA8F77'), 2))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(int(rx - 8), int(ry - 8), 16, 16)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor('#4938B8'))
            p.drawEllipse(int(sx - 6), int(sy - 6), 12, 12)
        p.setPen(QColor('#6C7284'))
        p.drawText(17, 22, 'Move towards the circle and click')
        p.drawText(17, self.height() - 13, 'Coral: raw    Purple: filtered')
        p.end()


class MainWindow(QMainWindow):
    preferences_changed = Signal(object)
    calibration_requested = Signal()
    assistance_changed = Signal(bool)

    def __init__(self, repo_root: Path):
        super().__init__()
        self.repo_root = Path(repo_root)
        self.prefs = load_settings()
        self.engine = AdaptiveEngine(self)
        self.steady = SteadyHandController()
        self.speech = None
        self._speech_process = None
        self._syncing_engine = True
        self._nav = {}
        self._pages = {}
        self._feature_rows = {}
        self._sliders = {}
        self._detail_buttons = {}
        self._detail_pages = {}
        self._base_qss = Path(__file__).with_name('control_center_styles.qss').read_text(encoding='utf-8')
        self.tint_manager = ScreenTintManager(QApplication.instance())
        self._build_ui()
        self.tint_manager.register_window(self)
        self.engine.modules_changed.connect(self._on_external_modules_changed)
        self._apply_preferences_to_engine()
        self._syncing_engine = False
        self._refresh()
        self._navigate('home')
        self.setWindowTitle('AccessShift AI — Focus UI 2.0')
        self.setMinimumSize(760, 570)
        self.resize(1030, 750)
        self._apply_visual_preferences()

    def _build_ui(self):
        root = QWidget()
        root.setObjectName('appRoot')
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header = QFrame()
        header.setObjectName('topbar')
        header.setMinimumHeight(72)
        header_l = QHBoxLayout(header)
        header_l.setContentsMargins(28, 10, 28, 10)
        header_l.setSpacing(20)
        logo = txt('A', 'brandSymbol')
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo.setFixedSize(40, 40)
        header_l.addWidget(logo)
        brand = QVBoxLayout()
        brand.setSpacing(2)
        brand.addWidget(txt('AccessShift', 'brandName'))
        brand.addWidget(txt('ACCESSIBILITY ASSISTANT', 'brandSub'))
        header_l.addLayout(brand)
        header_l.addStretch(1)

        for key, name in (('home', 'Assist'), ('adjust', 'Settings'), ('try', 'Demo')):
            action = btn(name, 'navTab')
            action.setCheckable(True)
            action.setMinimumWidth(94)
            action.clicked.connect(lambda checked=False, k=key: self._navigate(k))
            action.setAccessibleName(name + ' page')
            self._nav[key] = action
            header_l.addWidget(action)
        header_l.addStretch(1)
        status = txt('LOCAL DEMO', 'statusTag')
        status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        status.setMinimumWidth(106)
        header_l.addWidget(status)
        layout.addWidget(header)

        self.stack = QStackedWidget()
        self.stack.setObjectName('pageStack')
        for key, builder in (('home', self._page_home),
                             ('adjust', self._page_adjust),
                             ('try', self._page_try)):
            page = builder()
            self._pages[key] = page
            self.stack.addWidget(page)
        layout.addWidget(self.stack, 1)
        foot = QFrame()
        foot.setObjectName('appFooter')
        fl = QHBoxLayout(foot)
        fl.setContentsMargins(28, 6, 28, 6)
        fl.addWidget(txt('Preferences saved on this computer', 'footerText'))
        fl.addStretch()
        fl.addWidget(txt('Focus UI 2.0', 'footerText'))
        layout.addWidget(foot)

    def _page(self, title, subtitle, eyebrow):
        area = QScrollArea()
        area.setObjectName('pageScroll')
        area.setWidgetResizable(True)
        area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        container = QWidget()
        container.setObjectName('scrollContent')
        wrap = QVBoxLayout(container)
        wrap.setContentsMargins(24, 20, 24, 25)
        wrap.setSpacing(0)
        body = QWidget()
        body.setObjectName('contentBody')
        body.setMaximumWidth(920)
        lay = QVBoxLayout(body)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(10)
        lay.addWidget(txt(eyebrow.upper(), 'eyebrow'))
        lay.addWidget(txt(title, 'pageTitle', wrap=True))
        lay.addWidget(txt(subtitle, 'pageDescription', wrap=True))
        center = QHBoxLayout()
        center.setContentsMargins(0, 0, 0, 0)
        center.addStretch(1)
        center.addWidget(body, 20)
        center.addStretch(1)
        wrap.addLayout(center)
        wrap.addStretch(1)
        area.setWidget(container)
        return area, lay

    def _page_home(self):
        page, lay = self._page('Make this computer easier to use',
                               'Turn on the tools you need. Fine-tune only if you want to.',
                               'YOUR SETUP')
        preset = QFrame()
        preset.setObjectName('presetBar')
        pl = QHBoxLayout(preset)
        pl.setContentsMargins(20, 10, 20, 10)
        pl.setSpacing(12)
        ptext = QVBoxLayout()
        ptext.setSpacing(3)
        ptext.addWidget(txt('Start with a preset', 'fieldLabel'))
        self.profile_hint = txt('Or choose your own combination below.', 'supportText', wrap=True)
        ptext.addWidget(self.profile_hint)
        pl.addLayout(ptext, 1)
        self.profile_combo = QComboBox()
        self.profile_combo.setMinimumWidth(188)
        self.profile_combo.setMaximumWidth(260)
        for key in ('custom', 'als', 'parkinsons', 'cognitive'):
            self.profile_combo.addItem(PROFILES[key]['label'], key)
        self.profile_combo.setAccessibleName('Accessibility preset')
        self.profile_combo.currentIndexChanged.connect(self._profile_selected)
        pl.addWidget(self.profile_combo)
        lay.addWidget(preset)

        heading = QHBoxLayout()
        heading.addWidget(txt('Your tools', 'sectionTitle'))
        heading.addStretch()
        heading.addWidget(txt('Preferences · not live service status', 'sectionHint', wrap=True))
        lay.addLayout(heading)
        list_card, lc = surface('toolList', 0, 0)
        for idx, (key, title, description, num) in enumerate(FEATURES):
            line = ToolLine(num, title, description)
            line.changed.connect(lambda active, k=key: self._change_module(k, active))
            self._feature_rows[key] = line
            lc.addWidget(line)
            if idx < len(FEATURES) - 1:
                divider = QFrame()
                divider.setObjectName('lineDivider')
                divider.setFixedHeight(1)
                lc.addWidget(divider)
        lay.addWidget(list_card)

        bottom = QHBoxLayout()
        bottom.setSpacing(10)
        bottom.addWidget(txt('All changes save automatically.', 'supportText'))
        bottom.addStretch(1)
        customize = btn('Fine-tune settings', 'primaryButton')
        customize.clicked.connect(lambda: self._navigate('adjust'))
        bottom.addWidget(customize)
        lay.addLayout(bottom)
        lay.addStretch(1)
        return page

    def _page_adjust(self):
        page, lay = self._page('Fine-tune your assistance',
                               'Changes apply immediately to AccessShift and the local demo.',
                               'SETTINGS')
        tabs, tab_lay = surface('tabsBar', 6, 6)
        horizontal = QHBoxLayout()
        horizontal.setSpacing(8)
        for key, name in DETAILS:
            action = btn(name, 'detailTab')
            action.setCheckable(True)
            action.clicked.connect(lambda checked=False, k=key: self._switch_detail(k))
            self._detail_buttons[key] = action
            horizontal.addWidget(action, 1)
        tab_lay.addLayout(horizontal)
        lay.addWidget(tabs)

        self.detail_host = QWidget()
        host_l = QVBoxLayout(self.detail_host)
        host_l.setContentsMargins(0, 0, 0, 0)
        host_l.setSpacing(0)
        for key, builder in (('appearance', self._detail_appearance),
                             ('mouse', self._detail_mouse),
                             ('eyes', self._detail_eyes),
                             ('voice', self._detail_voice)):
            widget = builder()
            self._detail_pages[key] = widget
            host_l.addWidget(widget)
            widget.hide()
        lay.addWidget(self.detail_host)
        lay.addStretch(1)
        self._switch_detail('appearance')
        return page

    def _detail_card(self, title, description=''):
        frame, l = surface('surface', 22, 14)
        l.addWidget(txt(title, 'cardTitle'))
        if description:
            l.addWidget(txt(description, 'supportText', wrap=True))
        return frame, l

    @staticmethod
    def _field_header(text):
        return txt(text, 'fieldLabel')

    def _slider(self, minimum, maximum, step, key, suffix):
        h = QHBoxLayout()
        h.setSpacing(14)
        control = QSlider(Qt.Orientation.Horizontal)
        control.setRange(minimum, maximum)
        control.setSingleStep(step)
        control.setPageStep(step)
        control.setMinimumHeight(36)
        control.setAccessibleName(key.replace('_', ' '))
        control.valueChanged.connect(lambda value, k=key: self._change_option(k, value))
        value = txt('', 'valuePill')
        value.setAlignment(Qt.AlignmentFlag.AlignCenter)
        value.setMinimumWidth(70)
        h.addWidget(control, 1)
        h.addWidget(value)
        self._sliders[key] = control, value, suffix
        return h

    def _detail_appearance(self):
        holder = QWidget()
        l = QVBoxLayout(holder)
        l.setContentsMargins(0, 0, 0, 0)
        l.setSpacing(14)
        main, m = self._detail_card('Text and layout')
        m.addWidget(self._field_header('Text size'))
        m.addLayout(self._slider(90, 160, 10, 'font_size_pct', '%'))
        m.addWidget(self._field_header('Colour and contrast'))
        self.color_combo = QComboBox()
        for name, key in (('Standard', 'standard'), ('High contrast', 'high_contrast'),
                          ('Warm', 'warm'), ('Cool', 'cool')):
            self.color_combo.addItem(name, key)
        self.color_combo.currentIndexChanged.connect(
            lambda _: self._change_option('color_profile', self.color_combo.currentData()))
        m.addWidget(self.color_combo)
        m.addWidget(self._field_header('Letter spacing'))
        m.addLayout(self._slider(0, 4, 1, 'letter_spacing_px', 'px'))
        self.simple_row = PreferenceRow('Simplify demo form', 'Guide the user through one step at a time.')
        self.simple_row.setObjectName('inlineToggle')
        self.simple_row.changed.connect(lambda v: self._change_option('reduce_complexity', v))
        m.addWidget(self.simple_row)
        l.addWidget(main)

        tint, t = self._detail_card('Optional colour tint', 'Tint is limited to the two AccessShift windows.')
        self.tint_row = PreferenceRow('Use window tint', 'Add a subtle tint without changing other apps.')
        self.tint_row.setObjectName('inlineToggle')
        self.tint_row.changed.connect(self._set_window_tint)
        t.addWidget(self.tint_row)
        tint_controls = QWidget()
        tc = QVBoxLayout(tint_controls)
        tc.setContentsMargins(0, 0, 0, 0)
        tc.setSpacing(12)
        tc.addWidget(self._field_header('Tint colour'))
        self.tint_color_combo = QComboBox()
        for name, key in (('Warm amber', 'warm'), ('Cool blue', 'cool'), ('Soft rose', 'rose')):
            self.tint_color_combo.addItem(name, key)
        self.tint_color_combo.currentIndexChanged.connect(
            lambda _: self._change_option('tint_color', self.tint_color_combo.currentData()))
        tc.addWidget(self.tint_color_combo)
        tc.addWidget(self._field_header('Tint strength'))
        tc.addLayout(self._slider(0, 20, 1, 'tint_opacity', '%'))
        t.addWidget(tint_controls)
        self.tint_controls = tint_controls
        l.addWidget(tint)
        preview, p = self._detail_card('Live reading preview')
        self.visual_preview = VisualPreview()
        p.addWidget(self.visual_preview)
        l.addWidget(preview)
        return holder

    def _detail_mouse(self):
        holder = QWidget()
        l = QVBoxLayout(holder)
        l.setContentsMargins(0, 0, 0, 0)
        l.setSpacing(14)
        card, c = self._detail_card('SteadyHand', 'These values affect the bundled mouse test.')
        c.addWidget(self._field_header('Stabilization strength'))
        c.addLayout(self._slider(0, 100, 5, 'tremor_strength', '%'))
        c.addWidget(self._field_header('Demo target size'))
        c.addLayout(self._slider(100, 200, 10, 'target_size_pct', '%'))
        b = btn('Go to mouse test', 'secondaryButton')
        b.clicked.connect(lambda: self._navigate('try'))
        c.addWidget(b, alignment=Qt.AlignmentFlag.AlignLeft)
        l.addWidget(card)
        return holder

    def _detail_eyes(self):
        holder = QWidget()
        l = QVBoxLayout(holder)
        l.setContentsMargins(0, 0, 0, 0)
        l.setSpacing(14)
        card, c = self._detail_card('Eye & blink control', 'Works when the camera module is connected.')
        self.blink_row = PreferenceRow('Blink to select', 'Confirm a target with a deliberate blink.')
        self.blink_row.setObjectName('inlineToggle')
        self.blink_row.changed.connect(lambda v: self._change_option('blink_select', v))
        c.addWidget(self.blink_row)
        c.addWidget(self._field_header('Dwell time'))
        c.addLayout(self._slider(600, 2000, 100, 'gaze_dwell_ms', ' ms'))
        calibrate = btn('Request calibration', 'secondaryButton')
        calibrate.clicked.connect(self._request_calibration)
        c.addWidget(calibrate, alignment=Qt.AlignmentFlag.AlignLeft)
        l.addWidget(card)
        return holder

    def _detail_voice(self):
        holder = QWidget()
        l = QVBoxLayout(holder)
        l.setContentsMargins(0, 0, 0, 0)
        l.setSpacing(14)
        card, c = self._detail_card('Speech output', 'A basic offline text-to-speech test.')
        c.addWidget(self._field_header('Speaking speed'))
        c.addLayout(self._slider(100, 220, 10, 'speech_rate', ' wpm'))
        c.addWidget(self._field_header('Message'))
        self.speech_input = QLineEdit('Hello, I am using AccessShift.')
        self.speech_input.setAccessibleName('Message to speak aloud')
        c.addWidget(self.speech_input)
        actions = QHBoxLayout()
        actions.setSpacing(10)
        self.speak_button = btn('Speak', 'primaryButton')
        self.speak_button.clicked.connect(self._speak)
        self.stop_speech_button = btn('Stop', 'secondaryButton')
        self.stop_speech_button.setEnabled(False)
        self.stop_speech_button.clicked.connect(self._stop_speech)
        actions.addWidget(self.speak_button)
        actions.addWidget(self.stop_speech_button)
        actions.addStretch(1)
        c.addLayout(actions)
        self.speech_status = txt('Voice module availability depends on your environment.', 'supportText', wrap=True)
        c.addWidget(self.speech_status)
        l.addWidget(card)
        return holder

    def _page_try(self):
        page, lay = self._page('Try it on a real form',
                               'See changes in a second window while you adjust your settings.',
                               'LIVE DEMO')
        demo, d = self._detail_card('Healthcare form preview', 'Fictional data only, nothing is submitted.')
        actions = QHBoxLayout()
        actions.setSpacing(12)
        self.launch_demo_button = btn('Open live preview', 'primaryButton')
        self.launch_demo_button.setEnabled(False)
        self.launch_demo_button.setToolTip('Waiting for local demo integration')
        self.reset_demo_button = btn('Show original form', 'secondaryButton')
        self.reset_demo_button.setEnabled(False)
        actions.addWidget(self.launch_demo_button)
        actions.addWidget(self.reset_demo_button)
        actions.addStretch(1)
        d.addLayout(actions)
        d.addWidget(txt('Open the preview, then go to Settings → Display to see it adapt.', 'supportText', wrap=True))
        lay.addWidget(demo)
        practice, p = self._detail_card('Mouse accuracy practice', 'Click the target to try simulated stabilization.')
        self.playground = TremorPlayground(self.steady)
        p.addWidget(self.playground)
        score = QHBoxLayout()
        score.setSpacing(10)
        self.test_score = txt('Hits: 0  ·  Misses: 0  ·  Accuracy: —', 'fieldLabel', wrap=True)
        score.addWidget(self.test_score, 1)
        reset = btn('Reset', 'secondaryButton')
        reset.clicked.connect(self.playground.reset_scores)
        score.addWidget(reset)
        p.addLayout(score)
        self.filter_report = txt('Simulation only; the test does not move the OS pointer.', 'supportText', wrap=True)
        benchmark = btn('Compare smoothing', 'secondaryButton')
        benchmark.clicked.connect(self._benchmark_filter)
        p.addWidget(benchmark, alignment=Qt.AlignmentFlag.AlignLeft)
        p.addWidget(self.filter_report)
        lay.addWidget(practice)
        lay.addStretch(1)
        self.playground.metrics_changed.connect(self._update_test_score)
        return page

    # --- Public integration API: unchanged names for team modules ---
    def set_demo_launcher(self, callback):
        self.launch_demo_button.clicked.connect(callback)
        self.launch_demo_button.setEnabled(True)
        self.launch_demo_button.setToolTip('')

    def _switch_detail(self, key):
        if key not in self._detail_pages:
            return
        for name, w in self._detail_pages.items():
            w.setVisible(name == key)
        for name, action in self._detail_buttons.items():
            action.setChecked(name == key)

    def _navigate(self, key, detail=None):
        legacy = {
            'overview': ('home', None), 'personalize': ('home', None),
            'interface': ('adjust', 'appearance'), 'steady': ('adjust', 'mouse'),
            'gaze': ('adjust', 'eyes'), 'speech': ('adjust', 'voice'),
            'test': ('try', None),
        }
        if key in legacy:
            key, suggested_detail = legacy[key]
            detail = detail or suggested_detail
        if key not in self._pages:
            return
        self.stack.setCurrentWidget(self._pages[key])
        for name, action in self._nav.items():
            action.setChecked(name == key)
        if detail:
            self._switch_detail(detail)

    def _profile_selected(self, _=None):
        key = self.profile_combo.currentData()
        if not key or key not in PROFILES:
            return
        self.prefs.profile = key
        if key != 'custom':
            for module in ('gaze_control', 'steady_hand', 'smart_interface', 'predictive_speech'):
                setattr(self.prefs, module, bool(PROFILES[key][module]))
        self.prefs.initial_setup_complete = True
        self._apply_preferences_to_engine()
        self._save()
        self._refresh()

    def _apply_preferences_to_engine(self):
        previous = self._syncing_engine
        self._syncing_engine = True
        try:
            self.engine.set_profile(self.prefs.profile)
            for key, *_ in FEATURES:
                self.engine.set_module(key, getattr(self.prefs, key))
        finally:
            self._syncing_engine = previous
        self.steady.strength = self.prefs.tremor_strength / 100.0
        self.steady.enabled = self.prefs.steady_hand and self.prefs.assistance_enabled

    def _on_external_modules_changed(self, flags):
        if self._syncing_engine:
            return
        self.prefs.profile = self.engine.profile.id
        for key, *_ in FEATURES:
            setattr(self.prefs, key, bool(getattr(flags, key)))
        self.steady.enabled = self.prefs.steady_hand and self.prefs.assistance_enabled
        self._save()
        self._refresh()

    def _change_module(self, key, value):
        setattr(self.prefs, key, bool(value))
        self.prefs.profile = 'custom'
        self.prefs.initial_setup_complete = True
        self._apply_preferences_to_engine()
        self._save()
        self._refresh()

    def _change_option(self, key, value):
        setattr(self.prefs, key, value)
        if key == 'tremor_strength':
            self.steady.strength = self.prefs.tremor_strength / 100.0
        self._save()
        self._refresh()

    def _set_window_tint(self, enabled):
        self.prefs.tint_enabled = bool(enabled)
        self._apply_visual_preferences()
        self._save()
        self._refresh()

    def _save(self):
        save_settings(self.prefs)
        self.preferences_changed.emit(self.prefs.as_dict())

    def _refresh(self):
        self.profile_combo.blockSignals(True)
        idx = self.profile_combo.findData(self.prefs.profile)
        self.profile_combo.setCurrentIndex(idx if idx >= 0 else 0)
        self.profile_combo.blockSignals(False)
        self.profile_hint.setText(PROFILES.get(self.prefs.profile, PROFILES['custom'])['description'])
        for key, row in self._feature_rows.items():
            row.set_value(getattr(self.prefs, key))
        self.simple_row.set_value(self.prefs.reduce_complexity)
        self.blink_row.set_value(self.prefs.blink_select)
        self.tint_row.set_value(self.prefs.tint_enabled)
        self.tint_controls.setVisible(bool(self.prefs.tint_enabled))
        for key, (slider, display, suffix) in self._sliders.items():
            v = int(getattr(self.prefs, key))
            slider.blockSignals(True)
            slider.setValue(v)
            slider.blockSignals(False)
            display.setText(f'{v}{suffix}')
        for combo, key in ((self.color_combo, 'color_profile'),
                           (self.tint_color_combo, 'tint_color')):
            combo.blockSignals(True)
            index = combo.findData(getattr(self.prefs, key))
            combo.setCurrentIndex(max(0, index))
            combo.blockSignals(False)
        self._apply_visual_preferences()

    def _apply_visual_preferences(self):
        apply_accessshift_appearance(self, self._base_qss,
                                     self.prefs.font_size_pct, self.prefs.color_profile)
        self.visual_preview.set_preferences(self.prefs.font_size_pct,
                                            self.prefs.color_profile,
                                            self.prefs.letter_spacing_px)
        self.tint_manager.update(color=self.prefs.tint_color, opacity=self.prefs.tint_opacity)
        if self.prefs.tint_enabled:
            self.tint_manager.enable()
        else:
            self.tint_manager.disable()

    def _request_calibration(self):
        self.calibration_requested.emit()
        QMessageBox.information(self, 'Calibration',
                                'Calibration requested. The gaze module must supply the webcam workflow.')

    # Speech process: intentionally non-blocking; speech service remains separate.
    def _speak(self):
        message = self.speech_input.text().strip()
        if not message:
            self.speech_status.setText('Enter a message first.')
            return
        if not self.prefs.predictive_speech:
            self.speech_status.setText('Enable Communication on the Assist page first.')
            return
        self._stop_speech()
        proc = QProcess(self)
        proc.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        proc.finished.connect(self._on_speech_finished)
        proc.errorOccurred.connect(self._on_speech_error)
        proc.start(sys.executable, ['-m', 'accessshift.ui.speech_worker'])
        if not proc.waitForStarted(1500):
            self.speech_status.setText('Could not start speech.')
            proc.deleteLater()
            return
        self._speech_process = proc
        proc.write(json.dumps({'text': message, 'rate': self.prefs.speech_rate}).encode('utf-8'))
        proc.closeWriteChannel()
        self.speak_button.setEnabled(False)
        self.stop_speech_button.setEnabled(True)
        self.speech_status.setText('Speaking…')

    def _stop_speech(self):
        proc = self._speech_process
        if proc is not None:
            self._speech_process = None
            proc.blockSignals(True)
            if proc.state() != QProcess.ProcessState.NotRunning:
                proc.kill()
                proc.waitForFinished(1200)
            proc.deleteLater()
        if hasattr(self, 'speak_button'):
            self.speak_button.setEnabled(True)
            self.stop_speech_button.setEnabled(False)
        if hasattr(self, 'speech_status'):
            self.speech_status.setText('Ready')

    def _on_speech_finished(self, code, status):
        proc = self.sender()
        if proc is not self._speech_process:
            return
        output = bytes(proc.readAllStandardOutput()).decode('utf-8', 'replace').strip()
        self._speech_process = None
        self.speak_button.setEnabled(True)
        self.stop_speech_button.setEnabled(False)
        self.speech_status.setText('Finished.' if code == 0 else
                                   'Speech unavailable: ' + (output[-160:] or 'Backend error'))
        proc.deleteLater()

    def _on_speech_error(self, error):
        if self.sender() is self._speech_process:
            self.speech_status.setText('Speech backend could not start.')

    def _benchmark_filter(self):
        try:
            raw, filtered = [], []
            controller = SteadyHandController(strength=self.prefs.tremor_strength / 100)
            controller.enabled = True
            for i in range(240):
                t = .02 * (i + 1)
                x = 210. + 12 * math.sin(23*t) + 5 * math.sin(41*t)
                y = 120. + 12 * math.cos(27*t) + 5 * math.cos(38*t)
                sx, sy = controller.stabilize(x, y, t)
                if i >= 50:
                    raw.append(math.dist((x, y), (210., 120.)) ** 2)
                    filtered.append(math.dist((sx, sy), (210., 120.)) ** 2)
            a = math.sqrt(sum(raw)/len(raw))
            b = math.sqrt(sum(filtered)/len(filtered))
            delta = (1 - b/a)*100 if a else 0
            self.filter_report.setText(
                f'Simulated error: {a:.1f}px raw → {b:.1f}px filtered '
                f'({delta:+.1f}% reduction). This does not measure latency or clinical benefit.')
        except Exception as exc:
            self.filter_report.setText('Test unavailable: ' + str(exc))

    def _update_test_score(self, hits, misses):
        total = hits + misses
        self.test_score.setText(
            f'Hits: {hits}    Misses: {misses}    Accuracy: {hits/total:.0%}' if total
            else 'Hits: 0    Misses: 0    Accuracy: —')

    def closeEvent(self, event):
        self._stop_speech()
        self.tint_manager.disable()
        super().closeEvent(event)
