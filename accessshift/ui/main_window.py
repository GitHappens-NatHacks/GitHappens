"""Application window with an optional local healthcare demo.

This module preserves the public MainWindow class imported by accessshift.app.
The demo has its own window and listens to preference changes in real time.
"""
from __future__ import annotations

from pathlib import Path
from accessshift.ui.control_center import MainWindow as ControlCenter
from accessshift.ui.healthcare_demo_window import HealthcareDemoWindow


class MainWindow(ControlCenter):
    def __init__(self, repo_root: Path):
        super().__init__(repo_root)
        self._healthcare_demo: HealthcareDemoWindow | None = None
        self.set_demo_launcher(self._open_healthcare_demo)
        self.reset_demo_button.clicked.connect(self._show_original)
        self.preferences_changed.connect(self._update_live_demo)

    def _open_healthcare_demo(self):
        if self._healthcare_demo is None:
            self._healthcare_demo = HealthcareDemoWindow(
                self.repo_root, smart_interface_enabled=False, parent=self)
            self.tint_manager.register_window(self._healthcare_demo)
            self._healthcare_demo.enter_baseline()
        elif not self._healthcare_demo.isVisible():
            # An explicit new demo session begins from an original baseline.
            self._healthcare_demo.enter_baseline()
        self._healthcare_demo.show()
        self._healthcare_demo.raise_()
        self._healthcare_demo.activateWindow()
        self.reset_demo_button.setEnabled(True)
        self._navigate('adjust', 'appearance')

    def _show_original(self):
        if self._healthcare_demo is not None:
            self._healthcare_demo.enter_baseline()
            self._healthcare_demo.show()
            self._healthcare_demo.raise_()

    def _update_live_demo(self, settings):
        if self._healthcare_demo is not None and self._healthcare_demo.isVisible():
            self._healthcare_demo.apply_preferences(dict(settings))


__all__ = ['MainWindow']
