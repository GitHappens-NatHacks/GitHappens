"""AccessShift control center + a separate, live-updating healthcare preview.

The control center stays open. One modeless window holds the ORIGINAL local
healthcare form, and reacts to preference changes emitted by control_center.py.
No browser extensions or third-party website adaptation are used.
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel
from accessshift.ui.control_center import MainWindow as ControlCenterWindow
from accessshift.ui.control_center_components import button, card, label
from accessshift.ui.healthcare_demo_window import HealthcareDemoWindow


class MainWindow(ControlCenterWindow):
    def __init__(self, repo_root: Path):
        super().__init__(repo_root=repo_root)
        self._healthcare_demo: HealthcareDemoWindow | None = None
        self._add_local_demo_entries()
        self._add_demo_toolbar_button()
        # Existing control center signal: emitted on every setting edit.
        # Use it instead of reading a file on a timer or polling the UI.
        self.preferences_changed.connect(self._update_live_demo)

    def _add_demo_toolbar_button(self) -> None:
        shortcut = button('Open Demo Lab  ↗', 'secondaryButton')
        shortcut.setToolTip('Open the separate, local healthcare demo window')
        shortcut.setMinimumHeight(36)
        shortcut.clicked.connect(self._open_healthcare_demo)
        self.top_bar_layout.insertWidget(self.top_bar_layout.count() - 1, shortcut)

    def _add_local_demo_entries(self) -> None:
        # Retain the Demo Lab launcher in its own testing tab.
        test_page = self._pages['test']
        test_layout = test_page.widget().layout()
        demo, column = card(name='innerCard', margins=19, spacing=10)
        column.addWidget(label('Healthcare Demo Lab · live SmartInterface', 'sectionTitle'))
        column.addWidget(label(
            'Open a separate fictional healthcare form. AccessShift stays open on SmartInterface settings: '
            'change a slider or theme and watch the same form update instantly.',
            'bodyText', True))
        launch = button('Launch healthcare preview  ↗', 'primaryButton')
        launch.setAccessibleName('Open live local healthcare form preview')
        launch.clicked.connect(self._open_healthcare_demo)
        column.addWidget(launch, alignment=Qt.AlignmentFlag.AlignLeft)
        test_layout.insertWidget(4, demo)

        # Shortcut from the actual preferences page, so the first window can
        # remain on the settings controls while the second stays open.
        preferences_page = self._pages['interface']
        # The SmartInterface page is the live control panel for the preview.
        pref_layout = preferences_page.widget().layout()
        preview_card, pl = card(name='innerCard', margins=18, spacing=9)
        pl.addWidget(label('Live healthcare preview', 'sectionTitle'))
        pl.addWidget(label(
            'Keep this window open alongside a fictional appointment form. Changes to text size, colour, '
            'tint, layout and target size apply immediately without resetting entered data.',
            'bodyText', True))
        open_button = button('Open separate demo window  ↗', 'secondaryButton')
        open_button.clicked.connect(self._open_healthcare_demo)
        pl.addWidget(open_button, alignment=Qt.AlignmentFlag.AlignLeft)
        # Insert immediately before the preferences option cards.
        pref_layout.insertWidget(4, preview_card)

    def _open_healthcare_demo(self) -> None:
        # Focus the SmartInterface settings in the FIRST window.
        self._navigate('interface')
        if self._healthcare_demo is None:
            self._healthcare_demo = HealthcareDemoWindow(
                self.repo_root, smart_interface_enabled=False, parent=self)
            # Explicitly register this one extra AccessShift-owned window; never monitors.
            self.tint_manager.register_window(self._healthcare_demo)
        # Always begin at the original baseline to make the comparison obvious.
        # The first manual preference change enables the live adaptation.
        self._healthcare_demo.enter_baseline()
        self._healthcare_demo.show()
        self._healthcare_demo.raise_()
        self._healthcare_demo.activateWindow()

    def _update_live_demo(self, settings: object) -> None:
        if self._healthcare_demo is not None and self._healthcare_demo.isVisible():
            # No replacement of fields, no reload, no network operations.
            self._healthcare_demo.apply_preferences(dict(settings))


import os
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from accessshift.engine.adaptive_engine import AdaptiveEngine
from accessshift.engine.profiles import PROFILES
from accessshift.modules.speech.tts import SpeechEngine
from accessshift.modules.steadyhand.controller import SteadyHandController
from accessshift.ui.gaze_grid import GazeGridPanel
from accessshift.ui.gaze_mode import GazeMode
from accessshift.ui.portal_view import PortalView


class MainWindow(QMainWindow):
    def __init__(self, repo_root: Path):
        super().__init__()
        self.repo_root = repo_root
        self.engine = AdaptiveEngine(self)
        self.steady = SteadyHandController()
        self.speech = SpeechEngine()

        self.setWindowTitle("AccessShift AI")
        self.resize(1100, 720)

        root = QWidget()
        self.setCentralWidget(root)
        layout = QHBoxLayout(root)

        self.sidebar = QWidget()  # hidden while GazeControl is on (focus mode)
        side = QVBoxLayout(self.sidebar)
        side.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.sidebar, 1)

        side.addWidget(QLabel("AccessShift AI"))
        side.addWidget(QLabel("Adaptive Interaction Engine"))

        self.profile_list = QListWidget()
        for profile in PROFILES.values():
            item = QListWidgetItem(profile.label)
            item.setData(Qt.UserRole, profile.id)
            self.profile_list.addItem(item)
        self.profile_list.currentItemChanged.connect(self._on_profile_selected)
        side.addWidget(self.profile_list)

        self.chk_gaze = QCheckBox("GazeControl")
        self.chk_smart = QCheckBox("SmartInterface")
        self.chk_steady = QCheckBox("SteadyHand")
        self.chk_speech = QCheckBox("Predictive speech")
        for chk in (self.chk_gaze, self.chk_smart, self.chk_steady, self.chk_speech):
            side.addWidget(chk)

        self.chk_gaze.toggled.connect(lambda v: self.engine.set_module("gaze_control", v))
        self.chk_smart.toggled.connect(lambda v: self.engine.set_module("smart_interface", v))
        self.chk_steady.toggled.connect(self._on_steady_toggled)
        self.chk_speech.toggled.connect(lambda v: self.engine.set_module("predictive_speech", v))

        side.addWidget(QLabel("SteadyHand strength"))
        self.strength = QSlider(Qt.Horizontal)
        self.strength.setRange(0, 200)
        self.strength.setValue(int(self.steady.strength * 100))
        self.strength.valueChanged.connect(self._on_strength)
        side.addWidget(self.strength)

        self.chk_tremor = QCheckBox("Simulate tremor (demo)")
        self.chk_tremor.toggled.connect(self._on_tremor)
        side.addWidget(self.chk_tremor)

        self.btn_toggle_portal = QPushButton("Toggle SmartInterface layout")
        self.btn_toggle_portal.clicked.connect(self._toggle_portal_mode)
        side.addWidget(self.btn_toggle_portal)

        self.btn_speak = QPushButton("Speak confirmation")
        self.btn_speak.clicked.connect(lambda: self.speech.speak("Appointment confirmed"))
        side.addWidget(self.btn_speak)

        self.btn_system_mouse = QPushButton("Enable system mouse (pynput)")
        self.btn_system_mouse.clicked.connect(self._enable_system_mouse)
        side.addWidget(self.btn_system_mouse)

        self.status = QLabel("Ready")
        self.status.setWordWrap(True)
        side.addWidget(self.status)

        side.addStretch(1)

        # Gaze bar: only shown in gaze focus mode; every control here is gaze-clickable.
        self.gaze_bar = QWidget()
        bar = QHBoxLayout(self.gaze_bar)
        bar.setContentsMargins(0, 0, 0, 0)
        self.btn_recalibrate_gaze = QPushButton("Recalibrate gaze")
        self.btn_gaze_source = QPushButton()
        self.gaze_status = QLabel()
        self.gaze_status.setWordWrap(True)
        self.btn_exit_gaze = QPushButton("✕  Exit gaze control\n(or close your eyes for 3 s)")
        self.btn_exit_gaze.clicked.connect(lambda: self.chk_gaze.setChecked(False))
        bar.addWidget(self.btn_recalibrate_gaze, 1)
        bar.addWidget(self.btn_gaze_source, 1)
        bar.addWidget(self.gaze_status, 1)
        bar.addWidget(self.btn_exit_gaze, 2)  # wide target: easy to hit with gaze
        self.gaze_bar.hide()

        self.portal = PortalView(repo_root / "assets" / "portal")
        self.gaze_grid = GazeGridPanel(self.portal)  # 2x2 squares mirroring the portal, gaze mode only
        self.gaze_grid.hide()
        main = QVBoxLayout()
        main.addWidget(self.gaze_bar)
        main.addWidget(self.portal, 1)
        main.addWidget(self.gaze_grid, 1)
        layout.addLayout(main, 3)

        self.gaze = GazeMode(self)  # GazeControl: camera, gaze cursor, calibration, metrics
        self.gaze.status.connect(self.status.setText)
        self.gaze.status.connect(self.gaze_status.setText)
        self.gaze.exit_requested.connect(lambda: self.chk_gaze.setChecked(False))
        self.btn_recalibrate_gaze.clicked.connect(self.gaze.request_recalibrate)
        self.btn_gaze_source.clicked.connect(self.gaze.toggle_source)
        self.gaze.source_changed.connect(self._show_gaze_source)
        self._show_gaze_source(self.gaze.controller.source)

        self.engine.modules_changed.connect(self._sync_module_checks)
        self.engine.set_profile("parkinsons")
        self._select_profile_row("parkinsons")

        cam = os.getenv("GAZE_CAMERA_INDEX", "0")
        self.status.setText(f"Profile: Parkinson's · camera index {cam}")

    def _select_profile_row(self, profile_id: str) -> None:
        for i in range(self.profile_list.count()):
            item = self.profile_list.item(i)
            if item.data(Qt.UserRole) == profile_id:
                self.profile_list.setCurrentItem(item)
                break

    def _on_profile_selected(self, current, _previous) -> None:
        if current is None:
            return
        profile_id = current.data(Qt.UserRole)
        self.engine.set_profile(profile_id)
        self.status.setText(f"Profile: {current.text()}")

    def _sync_module_checks(self, modules) -> None:
        for chk, value in (
            (self.chk_gaze, modules.gaze_control),
            (self.chk_smart, modules.smart_interface),
            (self.chk_steady, modules.steady_hand),
            (self.chk_speech, modules.predictive_speech),
        ):
            chk.blockSignals(True)
            chk.setChecked(value)
            chk.blockSignals(False)
        self.steady.enabled = modules.steady_hand
        # Gaze focus mode: no sidebar, simple booking flow, gaze bar with Exit.
        self.sidebar.setVisible(not modules.gaze_control)
        self.gaze_bar.setVisible(modules.gaze_control)
        self.portal.set_accessible(modules.smart_interface or modules.gaze_control)
        self.portal.setVisible(not modules.gaze_control)
        self.gaze_grid.setVisible(modules.gaze_control)
        self.gaze.set_enabled(modules.gaze_control)

    def _show_gaze_source(self, source: str) -> None:
        other = "Eyes" if source == "head" else "Head"
        self.btn_gaze_source.setText(f"Pointing with: {source.capitalize()}\n(switch to {other})")

    def _on_steady_toggled(self, enabled: bool) -> None:
        self.engine.set_module("steady_hand", enabled)
        self.steady.enabled = enabled

    def _on_strength(self, value: int) -> None:
        self.steady.strength = value / 100.0

    def _on_tremor(self, enabled: bool) -> None:
        self.steady.simulate_tremor = enabled

    def _toggle_portal_mode(self) -> None:
        self.portal.toggle_mode()
        self.status.setText(f"Portal mode: {self.portal.mode.value}")

    def _enable_system_mouse(self) -> None:
        ok = self.steady.try_enable_system_mouse()
        if ok:
            self.status.setText("System mouse controller ready (pynput)")
        else:
            QMessageBox.warning(
                self,
                "Pointer control",
                "Could not enable system mouse control. On macOS, grant Accessibility "
                "permission to your terminal or the AccessShift app, then try again.",
            )

    def closeEvent(self, event) -> None:
        self.gaze.set_enabled(False)  # release the camera
        super().closeEvent(event)
