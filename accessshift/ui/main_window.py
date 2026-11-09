"""Younify control center + the Demo Lab + GazeControl hands-free window.

The control center stays open. "Open Demo Lab" shows every feature in one
independent window that follows preference changes live (via preferences_changed).
The Head movement tab opens the full-screen hands-free booking window (head pointing).
"""
from __future__ import annotations

from pathlib import Path

from accessshift.ui.control_center import MainWindow as ControlCenterWindow
from accessshift.ui.demo_lab_window import DemoLabWindow
from accessshift.ui.gaze_booking_window import GazeBookingWindow


class MainWindow(ControlCenterWindow):
    def __init__(self, repo_root: Path):
        self.gaze_window: GazeBookingWindow | None = None
        self.demo_lab: DemoLabWindow | None = None
        super().__init__(repo_root=repo_root)
        # Existing control center signal: emitted on every setting edit.
        self.preferences_changed.connect(self._update_demo_lab)
        # Head movement / Eye and blink control: the toggle (or the Hands-free profile) opens the hands-free window.
        self.preferences_changed.connect(self._sync_gaze)

    # --- Demo Lab -------------------------------------------------------------------------------
    def _open_demo_lab(self, section: str = 'start') -> None:
        if self.demo_lab is None:
            self.demo_lab = DemoLabWindow(self, self.repo_root)
            # Explicitly register this one extra Younify-owned window; never monitors.
            self.tint_manager.register_window(self.demo_lab)
        self.demo_lab.apply_preferences(self.prefs.as_dict())
        self.demo_lab.show_section(section)
        if self.demo_lab.isMinimized():
            self.demo_lab.showNormal()
        self.demo_lab.show()
        self.demo_lab.raise_()
        self.demo_lab.activateWindow()

    def _update_demo_lab(self, settings: object) -> None:
        if self.demo_lab is not None:
            self.demo_lab.apply_preferences(dict(settings))

    def _navigate(self, key):
        super()._navigate(key)
        # Keep the hands-free page uncluttered.
        self._demo_shortcut.setVisible(key != 'gaze')

    # --- GazeControl ------------------------------------------------------------------------
    def _ensure_gaze_window(self) -> GazeBookingWindow:
        if self.gaze_window is None:
            self.gaze_window = GazeBookingWindow(self.repo_root)
            self.gaze_window.exit_requested.connect(self._exit_gaze)
            self.gaze_window.problem.connect(self._gaze_problem)
            self.gaze_window.gaze.source_changed.connect(lambda _s: self._refresh())
            self.tint_manager.register_window(self.gaze_window)
        return self.gaze_window

    def _gaze_source(self) -> str:
        return 'head'  # Younify points with the head only

    def _start_gaze(self, source: str = 'head') -> None:
        self._ensure_gaze_window()  # head pointing only
        if not self.prefs.gaze_control:
            self._change_module('gaze_control', True)
        else:
            self._refresh()

    def _sync_gaze(self, settings: object) -> None:
        settings = dict(settings)
        if settings.get('gaze_control'):
            self._ensure_gaze_window()
        if self.gaze_window is not None:
            # Hands-free settings and the app's colour setting, applied live.
            self.gaze_window.apply_theme(str(settings.get('color_profile', 'standard')))
            self.gaze_window.apply_settings(settings.get('gaze_dwell_ms', 1100), settings.get('blink_select', True))
        if settings.get('gaze_control'):
            self.gaze_notice.hide()  # starting again clears any old message
            self.gaze_window.start()  # no-op if already running: other settings never restart the camera
        elif self.gaze_window is not None:
            self.gaze_window.stop()

    def _exit_gaze(self) -> None:
        if self.prefs.gaze_control:
            self._change_module('gaze_control', False)  # updates the toggle, saves, stops gaze
        self._bring_to_front()

    def _bring_to_front(self) -> None:
        if self.isMinimized():
            self.showNormal()
        self.raise_()
        self.activateWindow()

    def _gaze_problem(self, message: str) -> None:
        """Hands-free stopped (e.g. Esc during calibration): back to its settings page, explained."""
        self._exit_gaze()
        if self.gaze_window is not None:
            self.gaze_window.stop()
        self._navigate('gaze')
        self.gaze_notice.setText(message)
        self.gaze_notice.show()
        self._bring_to_front()

    def _request_calibration(self) -> None:
        """Replaces the control center's "integration pending" placeholder."""
        if not self.prefs.gaze_control:
            self._change_module('gaze_control', True)
        if self.gaze_window is not None:
            self.gaze_window.recalibrate()

    def closeEvent(self, event) -> None:
        if self.gaze_window is not None:
            self.gaze_window.stop()  # release the camera
        if self.demo_lab is not None:
            self.demo_lab.close()
        super().closeEvent(event)


__all__ = ['MainWindow']
