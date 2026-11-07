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
    QFrame, QGridLayout, QHBoxLayout, QLabel, QLineEdit, QMainWindow,
    QMessageBox, QPushButton, QScrollArea, QSlider, QStackedWidget,
    QVBoxLayout, QWidget,
)

from accessshift.engine.adaptive_engine import AdaptiveEngine
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
        self._syncing_engine = True
        self._build_ui()
        self.engine.modules_changed.connect(self._on_external_modules_changed)
        self._apply_preferences_to_engine()
        self._syncing_engine = False
        self._refresh()
        self._navigate('overview' if self.prefs.initial_setup_complete else 'personalize')
        self.resize(1200, 790)
        self.setMinimumSize(930, 640)
        self.setWindowTitle('AccessShift AI  |  Accessibility Control Center')
        style = Path(__file__).with_name('control_center_styles.qss')
        self.setStyleSheet(style.read_text(encoding='utf-8'))

    def _build_ui(self):
        root = QWidget()
        root.setObjectName('appRoot')
        self.setCentralWidget(root)
        outer = QHBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        side = QFrame()
        side.setObjectName('sidebar')
        side.setFixedWidth(237)
        side_l = QVBoxLayout(side)
        side_l.setContentsMargins(18, 27, 18, 22)
        side_l.setSpacing(9)
        brand = QHBoxLayout()
        mark = label('A', 'logoMark')
        mark.setFixedSize(43, 43)
        mark.setAlignment(Qt.AlignmentFlag.AlignCenter)
        brand.addWidget(mark)
        text_l = QVBoxLayout()
        text_l.setSpacing(2)
        text_l.addWidget(label('AccessShift', 'brandName'))
        text_l.addWidget(label('AI ACCESSIBILITY', 'brandSub'))
        brand.addLayout(text_l)
        side_l.addLayout(brand)
        side_l.addSpacing(28)
        side_l.addWidget(label('WORKSPACE', 'sideSection'))
        nav_entries = [
            ('overview', '◫   Overview'),
            ('personalize', '✦   My preferences'),
            ('gaze', '◎   Eye & blink control'),
            ('steady', '⌁   Mouse stability'),
            ('interface', '▤   Interface & speech'),
            ('test', '◉   Test & preview'),
        ]
        for key, text in nav_entries:
            btn = button(text, 'navButton')
            btn.setCheckable(True)
            btn.setMinimumHeight(46)
            btn.clicked.connect(lambda _, k=key: self._navigate(k))
            side_l.addWidget(btn)
            self._nav[key] = btn
        side_l.addStretch()
        info, info_l = card(name='innerCard', margins=12, spacing=5)
        info_l.addWidget(label('●  LOCAL PREFERENCES', 'goodPill'))
        info_l.addWidget(label('Saved on this device. No cloud account required.', 'micro', True))
        side_l.addWidget(info)
        side_l.addSpacing(8)
        side_l.addWidget(label('GitHappens  •  natHacks 2026', 'sidebarFoot'))
        outer.addWidget(side)

        right = QWidget()
        right_l = QVBoxLayout(right)
        right_l.setContentsMargins(0, 0, 0, 0)
        right_l.setSpacing(0)
        self.stack = QStackedWidget()
        right_l.addWidget(self.stack, 1)
        for key, method in [
            ('overview', self._page_overview),
            ('personalize', self._page_personalize),
            ('gaze', self._page_gaze),
            ('steady', self._page_steady),
            ('interface', self._page_interface),
            ('test', self._page_test),
        ]:
            page = method()
            self._pages[key] = page
            self.stack.addWidget(page)
        foot = QFrame()
        foot.setObjectName('footerBar')
        fl = QHBoxLayout(foot)
        fl.setContentsMargins(33, 11, 33, 11)
        fl.addWidget(label('AccessShift AI  ·  Universal desktop interface', 'footerText'))
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
        page, lay = self._page('YOUR ACCESSIBILITY COMPANION', 'Your control center',
                               'Set up the assistance you need, then continue using your computer.')
        hero, hl = card(name='hero', margins=27, spacing=12)
        hl.addWidget(label('PERSONALIZED DIGITAL ACCESS', 'heroEyebrow'))
        hl.addWidget(label('Technology that adapts to you.', 'heroTitle'))
        hl.addWidget(label('One place to configure eye navigation, steadier mouse control, and simpler interfaces.',
                           'heroDescription', True))
        hr = QHBoxLayout()
        self.overview_profile = label('Your setup: Custom', 'heroBadge')
        hr.addWidget(self.overview_profile)
        hr.addStretch()
        edit = button('Edit my setup', 'heroButton')
        edit.clicked.connect(lambda: self._navigate('personalize'))
        hr.addWidget(edit)
        hl.addLayout(hr)
        lay.addWidget(hero)
        row = QHBoxLayout()
        self.stat_modules = StatCard('SELECTED MODULES', '0 / 4', 'Configured for your preferences')
        self.stat_profile = StatCard('INTERACTION STYLE', 'Custom', 'Choose a profile at any time')
        self.stat_platform = StatCard('APP PLATFORM', 'Mac + Win', 'Powered by Qt / PySide6')
        for w in (self.stat_modules, self.stat_profile, self.stat_platform):
            row.addWidget(w, 1)
        lay.addLayout(row)
        self._section(lay, 'Your accessibility tools', 'All your preferences are adjustable and saved automatically.')
        grid = QGridLayout()
        grid.setSpacing(13)
        self.overview_module_labels = {}
        for i, (key, title, desc) in enumerate([
            ('gaze_control', 'Eye & blink control', 'Webcam-based hands-free navigation'),
            ('steady_hand', 'SteadyHand', 'Mouse smoothing and easier targeting'),
            ('smart_interface', 'SmartInterface', 'Simpler layouts and larger controls'),
            ('predictive_speech', 'Communication', 'Speech and assisted text input'),
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
        nl.addWidget(label('Integration status', 'cardTitle'))
        nl.addWidget(label('This control center saves preferences and operates the in-app tremor test. '
                           'Webcam navigation, system-wide pointer correction and website transformation '
                           'require their respective modules to be connected.', 'bodyText', True))
        lay.addWidget(note)
        lay.addStretch()
        return page

    def _page_personalize(self):
        page, lay = self._page('STEP 01  /  MAKE IT YOURS', 'Choose what works for you',
                               'Start with a suggested setup or make your own combination. Nothing here is a medical diagnosis.')
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
            ('smart_interface', 'Simplify interfaces', 'Use larger controls and less visual complexity in supported integrations.'),
            ('predictive_speech', 'Communication support', 'Enable text prediction hooks and text-to-speech.'),
        ]
        for key, name, desc in options:
            r = PreferenceRow(name, desc)
            r.changed.connect(lambda value, k=key: self._change_module(k, value))
            self._toggle_rows[key] = r
            lay.addWidget(r)
        actions = QHBoxLayout()
        actions.addStretch()
        done = button('Save setup & go to overview  →', 'primaryButton')
        done.clicked.connect(self._finish_setup)
        actions.addWidget(done)
        lay.addLayout(actions)
        lay.addStretch()
        return page

    def _page_gaze(self):
        page, lay = self._page('HANDS-FREE INTERACTION', 'Eye & blink control',
                               'Configure your preferred gaze selection behavior before connecting camera tracking.')
        row = PreferenceRow('Use eye navigation', 'Allow gaze tracking as an interaction method.')
        row.changed.connect(lambda v: self._change_module('gaze_control', v))
        self.gaze_toggle = row
        lay.addWidget(row)
        gaze_box, gb = card()
        gb.addWidget(label('How should selection work?', 'sectionTitle'))
        self.blink_row = PreferenceRow('Blink to select', 'Use a deliberate blink as confirmation.')
        self.blink_row.changed.connect(lambda v: self._change_option('blink_select', v))
        gb.addWidget(self.blink_row)
        gb.addWidget(label('Dwell time', 'cardTitle'))
        gb.addWidget(label('How long to look at a target before it becomes selected.', 'bodyText'))
        self.dwell_slider, dwell_row = self._slider(600, 2000, 100, 'gaze_dwell_ms', 'ms')
        gb.addLayout(dwell_row)
        lay.addWidget(gaze_box)
        cal, cl = card(name='innerCard')
        cl.addWidget(label('Camera calibration', 'sectionTitle'))
        cl.addWidget(label('A future gaze worker will provide webcam preview, calibration points, '
                           'and gaze accuracy. The settings here are ready for that integration.', 'bodyText', True))
        cal_btn = button('Connect calibration module', 'secondaryButton')
        cal_btn.clicked.connect(self._request_calibration)
        cl.addWidget(cal_btn, alignment=Qt.AlignmentFlag.AlignLeft)
        lay.addWidget(cal)
        lay.addStretch()
        return page

    def _page_steady(self):
        page, lay = self._page('MOTION ASSISTANCE', 'Mouse stabilization',
                               'Tune the response to hand movement and reduce unwanted cursor jitter.')
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
        page, lay = self._page('CLEARER, CALMER INTERFACES', 'Interface & communication',
                               'Adjust layout preferences and communication assistance in one place.')
        row = PreferenceRow('Enable SmartInterface', 'Simplify supported applications and website integrations.')
        row.changed.connect(lambda v: self._change_module('smart_interface', v))
        self.interface_toggle = row
        lay.addWidget(row)
        options, ol = card()
        self.simple_row = PreferenceRow('Reduce complexity', 'Fewer competing controls and a guided step-by-step layout.')
        self.simple_row.changed.connect(lambda v: self._change_option('reduce_complexity', v))
        ol.addWidget(self.simple_row)
        ol.addWidget(label('Preferred text size', 'cardTitle'))
        self.font_slider, fr = self._slider(90, 160, 10, 'font_size_pct', '%')
        ol.addLayout(fr)
        ol.addWidget(label('These preferences are passed to supported interface adapters; '
                           'they cannot rewrite every third-party app by themselves.', 'bodyText', True))
        lay.addWidget(options)
        speak, spl = card()
        spl.addWidget(label('Speech & text assistance', 'sectionTitle'))
        self.speech_row = PreferenceRow('Enable communication support', 'Activate speech and predictive text settings.')
        self.speech_row.changed.connect(lambda v: self._change_module('predictive_speech', v))
        spl.addWidget(self.speech_row)
        spl.addWidget(label('Speech rate', 'cardTitle'))
        self.speech_slider, srl = self._slider(100, 220, 10, 'speech_rate', 'wpm')
        spl.addLayout(srl)
        spl.addWidget(label('Try a spoken phrase', 'cardTitle'))
        self.speech_input = QLineEdit('Hello, I am using AccessShift to communicate.')
        self.speech_input.setAccessibleName('Text to speak')
        spl.addWidget(self.speech_input)
        speak_button = button('Speak this text', 'primaryButton')
        speak_button.clicked.connect(self._speak)
        spl.addWidget(speak_button, alignment=Qt.AlignmentFlag.AlignLeft)
        lay.addWidget(speak)
        lay.addStretch()
        return page

    def _page_test(self):
        page, lay = self._page('TRY YOUR SETTINGS', 'Test & preview',
                               'An in-app demo for the mouse stabilizer. No system-wide cursor changes are made.')
        test, tl = card()
        tl.addWidget(label('SteadyHand • accuracy playground', 'sectionTitle'))
        tl.addWidget(label('Move the cursor into the area and click the purple target. '
                           'Compare the raw (coral) and smoothed (purple) indicators.', 'bodyText', True))
        self.playground = TremorPlayground(self.steady)
        tl.addWidget(self.playground)
        bars = QHBoxLayout()
        self.test_score = label('Hits: 0  •  Misses: 0  •  Accuracy: —', 'cardTitle')
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
        il.addWidget(label('This test demonstrates filtering; it is not a clinical performance assessment. '
                           'Live gaze calibration and website adaptation will appear here after integration.',
                           'bodyText', True))
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
        self.blink_row.set_value(self.prefs.blink_select)
        for k, (slider, text, suffix) in self._sliders.items():
            value = int(getattr(self.prefs, k))
            slider.blockSignals(True)
            slider.setValue(value)
            slider.blockSignals(False)
            text.setText(f'{value} {suffix}')
        self.footer_status.setText('✓  Preferences saved locally')

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
            if self.speech._engine is not None:
                self.speech._engine.setProperty('rate', self.prefs.speech_rate)
            self.speech.speak(msg)
        except Exception as exc:
            QMessageBox.warning(self, 'Speech unavailable', str(exc))

    def _update_test_score(self, hits, misses):
        n = hits + misses
        accuracy = f'{hits / n:.0%}' if n else '—'
        self.test_score.setText(f'Hits: {hits}  •  Misses: {misses}  •  Accuracy: {accuracy}')
