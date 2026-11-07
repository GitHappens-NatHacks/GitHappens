"""Primary AccessShift window: dashboard + portal + module status."""

from __future__ import annotations

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

        side = QVBoxLayout()
        layout.addLayout(side, 1)

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
        self.strength.setRange(0, 100)
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

        self.btn_recalibrate_gaze = QPushButton("Recalibrate gaze")
        side.addWidget(self.btn_recalibrate_gaze)

        self.status = QLabel("Ready")
        self.status.setWordWrap(True)
        side.addWidget(self.status)

        self.gaze = GazeMode(self)  # GazeControl: camera, gaze cursor, calibration, metrics
        self.gaze.status.connect(self.status.setText)
        self.btn_recalibrate_gaze.clicked.connect(self.gaze.recalibrate)
        side.addStretch(1)

        self.portal = PortalView(repo_root / "assets" / "portal")
        layout.addWidget(self.portal, 3)

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
        self.gaze.set_enabled(modules.gaze_control)
        if modules.smart_interface:
            self.portal.set_accessible(True)
        else:
            self.portal.set_accessible(False)

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
