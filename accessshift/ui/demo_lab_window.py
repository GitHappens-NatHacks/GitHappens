"""Younify Demo Lab: every feature in one window, ready to present.

A left rail lists Start here, SteadyHand, Head movement and SmartInterface.
Each page explains what to show and holds the working demo:
  - SmartInterface: the sample healthcare form, following the person's profile live,
    with an Original / With your settings comparison.
  - SteadyHand: the tremor practice canvas and 10-step accuracy trial.
  - Head movement: start the full-screen hands-free booking demo.
The window is independent of the control center, so both can stay open side by side.
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication, QButtonGroup, QFrame, QHBoxLayout, QPushButton, QScrollArea, QStackedWidget,
    QVBoxLayout, QWidget,
)

from accessshift.modules.steadyhand.controller import SteadyHandController
from accessshift.ui import icons
from accessshift.ui import theme as theme_mod
from accessshift.ui.control_center import PhotoHeader
from accessshift.ui.control_center_components import button, card, label
from accessshift.ui.healthcare_demo_window import HealthcareDemoWindow
from accessshift.ui.steadyhand_panel import SteadyHandTrialPanel

SECTIONS = (
    ('start', 'lab', 'Start here'),
    ('steady', 'steady', 'SteadyHand'),
    ('gaze', 'head', 'Head movement'),
    ('interface', 'interface', 'SmartInterface'),
)

RUN_ORDER = (
    ('steady', 'steady', 'SteadyHand', 'Hit small targets with a simulated tremor, then compare accuracy with and without help.', 'About 1 minute'),
    ('gaze', 'head', 'Head movement', 'Book an appointment hands-free by turning your head.', 'About 2 minutes'),
    ('interface', 'interface', 'SmartInterface', 'Turn a busy appointment form into large, calm, step-by-step screens.', 'About 1 minute'),
)
PHOTOS = {'lab': 'care-desk.jpg', 'steady': 'mouse-mat.jpg', 'head': 'webcam.jpg', 'interface': 'glasses-notes.jpg'}


class DemoLabWindow(QWidget):
    def __init__(self, host, repo_root: Path):
        super().__init__(None, Qt.WindowType.Window)
        self.host = host  # the control center: starts hands-free control, owns the settings
        self.repo_root = Path(repo_root)
        self.setObjectName('labRoot')
        self.setWindowTitle('Younify Demo Lab')
        self.setWindowIcon(theme_mod.logo_icon())
        self.resize(1280, 860)
        self.setMinimumSize(980, 680)
        self._settings: dict = dict(host.prefs.as_dict())
        self._tiles: list[icons.IconTile] = []
        self._headers: list[PhotoHeader] = []
        self._rail_buttons: dict[str, QPushButton] = {}
        self._pages: dict[str, QWidget] = {}
        self.steady = SteadyHandController()  # its own controller: the lab never disturbs the settings window
        self._build()
        self.apply_preferences(self._settings)
        self.show_section('start')
        self.stack.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setFocusProxy(self.stack)  # opening the lab does not draw a focus ring on the first rail button

    # ------------------------------------------------------------------ layout
    def _build(self) -> None:
        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        rail = QFrame()
        rail.setObjectName('rail')
        rail.setFixedWidth(250)
        rl = QVBoxLayout(rail)
        rl.setContentsMargins(16, 26, 16, 20)
        rl.setSpacing(4)
        self.rail_mark = icons.IconTile('lab', 40)
        top = QHBoxLayout()
        top.setSpacing(12)
        top.addWidget(self.rail_mark)
        top.addWidget(label('Demo Lab', 'railTitle'))
        top.addStretch(1)
        rl.addLayout(top)
        rl.addSpacing(8)
        rl.addWidget(label('Every Younify feature, ready to show.', 'railText', True))
        rl.addSpacing(18)
        group = QButtonGroup(self)
        for key, icon_name, title in SECTIONS:
            b = button(title, 'railButton')
            b.setCheckable(True)
            b.setMinimumHeight(44)
            b.setProperty('iconName', icon_name)
            b.clicked.connect(lambda _=False, k=key: self.show_section(k))
            group.addButton(b)
            rl.addWidget(b)
            self._rail_buttons[key] = b
        rl.addStretch(1)
        back = button('Back to Younify', 'railButton')
        back.setProperty('iconName', 'back')
        back.clicked.connect(self._back_to_app)
        self.back_button = back
        rl.addWidget(back)
        outer.addWidget(rail)

        self.stack = QStackedWidget()
        outer.addWidget(self.stack, 1)
        for key, builder in (('start', self._page_start), ('steady', self._page_steady),
                             ('gaze', self._page_gaze), ('interface', self._page_interface)):
            page = builder()
            self._pages[key] = page
            self.stack.addWidget(page)

    def _tile(self, name: str, size: int = 44) -> icons.IconTile:
        tile = icons.IconTile(name, size)
        self._tiles.append(tile)
        return tile

    def _page(self, icon_name: str, title: str, subtitle: str):
        scroller = QScrollArea()
        scroller.setWidgetResizable(True)
        scroller.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        body = QWidget()
        body.setObjectName('scrollContent')
        lay = QVBoxLayout(body)
        lay.setContentsMargins(40, 32, 40, 40)
        lay.setSpacing(18)
        header = PhotoHeader(PHOTOS.get(icon_name, 'care-desk.jpg'), title, subtitle)
        self._headers.append(header)
        lay.addWidget(header)
        lay.addSpacing(6)
        scroller.setWidget(body)
        return scroller, lay

    def _steps(self, steps: tuple[str, ...]) -> QFrame:
        box, bl = card(spacing=12)
        bl.addWidget(label('How to demo it', 'sectionTitle'))
        for i, text in enumerate(steps, 1):
            row = QHBoxLayout()
            row.setSpacing(14)
            row.addWidget(label(str(i), 'number'), 0, Qt.AlignmentFlag.AlignTop)
            row.addWidget(label(text, 'strongText', True), 1)
            bl.addLayout(row)
        return box

    # ------------------------------------------------------------------ pages
    def _page_start(self):
        page, lay = self._page('lab', 'Show Younify in three short demos',
                               'Pick a demo on the left, or follow the suggested order below. Every demo uses the '
                               'settings from your accessibility profile.')
        before, bl = card(name='band', margins=24, spacing=10)
        bl.addWidget(label('Before you start', 'sectionTitle'))
        for text in ('Connect a webcam and close other apps that might be using it.',
                     'Light your face from the front and sit about an arm\'s length from the screen.',
                     'On macOS, allow camera access for Terminal or Python the first time you are asked.'):
            row = QHBoxLayout()
            row.setSpacing(12)
            row.addWidget(self._tile('check', 26), 0, Qt.AlignmentFlag.AlignTop)
            row.addWidget(label(text, 'bandText', True), 1)
            bl.addLayout(row)
        lay.addWidget(before)

        lay.addSpacing(6)
        lay.addWidget(label('Suggested order', 'sectionTitle'))
        order, ol = card(margins=8, spacing=0)
        for i, (key, icon_name, title, what, length) in enumerate(RUN_ORDER):
            if i:
                line = QFrame()
                line.setObjectName('divider')
                ol.addWidget(line)
            row = QHBoxLayout()
            row.setContentsMargins(14, 14, 14, 14)
            row.setSpacing(16)
            row.addWidget(label(str(i + 1), 'number'))
            row.addWidget(self._tile(icon_name, 44))
            texts = QVBoxLayout()
            texts.setSpacing(3)
            texts.addWidget(label(title, 'cardTitle'))
            texts.addWidget(label(what, 'bodyText', True))
            row.addLayout(texts, 1)
            row.addWidget(label(length, 'micro'))
            go = button('Open', 'secondaryButton')
            go.setAccessibleName(f'Open the {title} demo')
            go.clicked.connect(lambda _=False, k=key: self.show_section(k))
            row.addWidget(go)
            ol.addLayout(row)
        lay.addWidget(order)
        lay.addStretch(1)
        return page

    def _page_interface(self):
        page, lay = self._page('interface', 'SmartInterface',
                               'A practice appointment form, simplified or original. It follows your profile live.')
        lay.addWidget(self._steps((
            'With SmartInterface on, the form opens as two calm steps. Fill them in and press Finish demo.',
            'Press "View original form" to show every field at once, then "Try simplified" to switch back.',
            'Change text size, spacing, colours or click target size in Younify. The form updates instantly '
            'and keeps what was typed.',
        )))
        bar, bl = card(spacing=10)
        row = QHBoxLayout()
        row.setSpacing(12)
        self.interface_summary = label('', 'bodyText', True)
        row.addWidget(self.interface_summary, 1)
        adjust = button('Adjust settings', 'secondaryButton')
        adjust.setToolTip('Open the SmartInterface page in Younify')
        adjust.clicked.connect(lambda: self._open_settings('interface'))
        row.addWidget(adjust, 0, Qt.AlignmentFlag.AlignVCenter)
        bl.addLayout(row)
        lay.addWidget(bar)

        self.smart_off_notice, nl = card(name='notice', margins=16, spacing=8)
        nrow = QHBoxLayout()
        nrow.addWidget(label('SmartInterface is off in your profile, so the form shows its original layout.',
                             'strongText', True), 1)
        turn_on = button('Turn SmartInterface on', 'primaryButton')
        turn_on.clicked.connect(lambda: self.host._change_module('smart_interface', True))
        nrow.addWidget(turn_on)
        nl.addLayout(nrow)
        lay.addWidget(self.smart_off_notice)

        self.healthcare = HealthcareDemoWindow(self.repo_root, smart_interface_enabled=False, parent=self, embedded=True)
        self.healthcare.setMinimumHeight(760)
        lay.addWidget(self.healthcare, 1)
        return page

    def _page_steady(self):
        page, lay = self._page('steady', 'SteadyHand',
                               'Steadier pointing and bigger click zones, measured with a 10-step booking trial.')
        lay.addWidget(self._steps((
            'Leave "Simulate shaky movement" on and choose Baseline (Raw input). Start a trial and click the steps.',
            'Choose Smoothing + Target assistance and run the same trial.',
            'Compare accuracy and time in the results. Export them if you want to keep a record.',
        )))
        demo, dl = card(spacing=12)
        self.steady_panel = SteadyHandTrialPanel(self.steady, int(self._settings.get('target_size_pct', 140)),
                                                 self.repo_root, self._settings)
        dl.addWidget(self.steady_panel)
        lay.addWidget(demo)
        lay.addStretch(1)
        return page

    def _page_gaze(self):
        page, lay = self._page('head', 'Head movement',
                               'Book an appointment hands-free by turning your head.')
        lay.addWidget(self._steps((
            'Press Start. Face the screen, then turn your head when the arrows ask (about 10 seconds).',
            'Turn toward an option and hold still until the ring fills, or blink slowly once it starts.',
            'Book the appointment and choose Close, or press Quit hands-free in the top bar at any time.',
        )))
        start, sl = card(margins=24, spacing=12)
        row = QHBoxLayout()
        row.setSpacing(12)
        self.head_button = button('Start the head movement demo', 'primaryButton')
        self.head_button.setMinimumHeight(60)
        self.head_button.setStyleSheet('QPushButton { font-size: 17px; }')
        self.head_button.clicked.connect(lambda: self._toggle_gaze('head'))
        row.addWidget(self.head_button)
        sl.addLayout(row)
        self.gaze_status = label('', 'bodyText', True)
        sl.addWidget(self.gaze_status)
        lay.addWidget(start)
        tips, tl = card(name='innerCard')
        tl.addWidget(label('Tip', 'cardTitle'))
        tl.addWidget(label('Light your face from the front. If the pointer drifts, use Recalibrate in the '
                           'full-screen view.', 'bodyText', True))
        lay.addWidget(tips)
        lay.addStretch(1)
        return page

    # ------------------------------------------------------------------ behaviour
    def show_section(self, key: str) -> None:
        key = key if key in self._pages else 'start'
        if self.steady_panel.trial_running and key != 'steady':
            self.steady_panel.abort_trial()
        self.stack.setCurrentWidget(self._pages[key])
        for k, b in self._rail_buttons.items():
            b.setChecked(k == key)
        if self.isVisible() and QApplication.focusWidget() in self._rail_buttons.values():
            self._rail_buttons[key].setFocus()  # keep the focus ring on the open section

    def _toggle_gaze(self, source: str) -> None:
        self.host._toggle_gaze(source)
        self._update_gaze_state()

    def _open_settings(self, page: str) -> None:
        self.host._navigate(page)
        self._back_to_app()

    def _back_to_app(self) -> None:
        host = self.host
        if host.isMinimized():
            host.showNormal()
        host.show()
        host.raise_()
        host.activateWindow()

    def _update_interface_summary(self) -> None:
        s = self._settings
        smart = bool(s.get('smart_interface', False))
        self.smart_off_notice.setVisible(not smart)
        theme_name = dict(theme_mod.THEME_LABELS).get(str(s.get('color_profile', 'standard')), 'Standard')
        if smart:
            self.interface_summary.setText(
                f"Using your settings: text {s.get('font_size_pct', 110)}%, letter spacing "
                f"{s.get('letter_spacing_px', 0)} px, {theme_name} colours, click targets {s.get('target_size_pct', 140)}%, "
                + ('step-by-step layout.' if s.get('reduce_complexity', True) else 'all fields at once.'))
        else:
            self.interface_summary.setText('Your settings would apply here once SmartInterface is on.')

    def _update_gaze_state(self) -> None:
        running = bool(self._settings.get('gaze_control', False))
        self.head_button.setText('Stop the demo' if running else 'Start the head movement demo')
        self.gaze_status.setText(
            'Running in the full-screen hands-free window.' if running else
            'Opens a full-screen hands-free booking window with large options.')

    def apply_preferences(self, settings: dict) -> None:
        self._settings = dict(settings)
        profile = str(settings.get('color_profile', 'standard'))
        t = theme_mod.theme(profile)
        self.setStyleSheet(theme_mod.stylesheet(int(settings.get('font_size_pct', 110)), profile))
        for tile in self._tiles:
            tile.set_colors(t.mint, t.primary)
        for header in self._headers:
            header.set_shade(t.sidebar)
        self.rail_mark.set_colors(t.primary, t.on_primary)
        for b in list(self._rail_buttons.values()) + [self.back_button]:
            b.setIcon(icons.icon(str(b.property('iconName')), t.sidebar_text, 20))
        self.healthcare.apply_preferences(self._settings)
        self.steady.strength = int(settings.get('tremor_strength', 50)) / 100.0
        self.steady_panel.set_target_size(int(settings.get('target_size_pct', 140)))
        self.steady_panel.set_theme(t)
        self.steady_panel.set_extra(self._settings)
        self._update_interface_summary()
        self._update_gaze_state()

    def closeEvent(self, event) -> None:
        if self.steady_panel.trial_running:
            self.steady_panel.abort_trial()
        super().closeEvent(event)
