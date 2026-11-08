"""GazeMode: everything the main window needs to turn GazeControl on and off.

Owns the GazeController (camera thread), the gaze cursor overlay, the camera
preview, the big high-contrast button style and the pitch metrics, so the main
window only calls set_enabled() / recalibrate(). Turning it off restores the
window exactly as it was.
"""

from __future__ import annotations

import math
import os
import time
from collections.abc import Callable

from PySide6.QtCore import QObject, QRect, QTimer, Signal
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QPushButton, QWidget

from accessshift.modules.gaze.controller import (
    EXIT_CLOSE_MS,
    EXIT_COUNTDOWN_FROM_MS,
    STATUS_NO_FACE,
    STATUS_TRACKING,
    GazeController,
)
from accessshift.modules.gaze.metrics import GazeMetrics
from accessshift.ui import gaze_style
from accessshift.ui.gaze_calibration_dialog import GazeCalibrationDialog
from accessshift.ui.gaze_camera_preview import GazeCameraPreview
from accessshift.ui.gaze_overlay import GazeOverlay

FINISH_BUTTON = "Book appointment"  # selecting this ends the timed booking task
ALERT_MS = 3000  # how long one-off alerts (e.g. calibration cancelled) stay up
FACE_ALERT_DELAY_MS = 1000  # turning toward an edge square can lose the face briefly


def _is_problem(status: str) -> bool:
    return status == STATUS_NO_FACE or status.startswith(("Camera", "Gaze tracking stopped"))


def _now_ms() -> int:
    return int(time.monotonic() * 1000)


EXIT_HINT = "Keep your eyes closed to exit hands-free control"
CALIBRATION_CANCELLED = (
    "Calibration was cancelled, so head movement control is off. "
    "Choose Start head control to try again."
)


class GazeMode(QObject):
    status = Signal(str)
    exit_requested = Signal()  # user held their eyes closed: the window should turn gaze off
    source_changed = Signal(str)  # "head" or "eyes"
    problem = Signal(str)  # hands-free can't continue (calibration cancelled, camera failed)

    def __init__(
        self,
        parent: QObject | None = None,
        screen_rect: QRect | None = None,
        tracker_factory: Callable[[], object] | None = None,
        calibrate_on_start: bool = True,
    ):
        super().__init__(parent)
        self._tracker_factory = tracker_factory
        self._calibrate_on_start = calibrate_on_start
        self._camera_index = int(os.getenv("GAZE_CAMERA_INDEX", "0"))
        source = os.getenv("GAZE_INPUT", "head")
        self._window = parent if isinstance(parent, QWidget) else None  # gets the big-button style
        self._window_geometry = None  # window size/position before gaze mode filled the screen
        self._calibrating = False  # only one calibration screen at a time
        self._face_missing = False
        self.palette = None  # app colour palette for the style and calibration screen
        self.controller = GazeController(screen_rect=screen_rect, parent=self)
        if source in ("head", "eyes"):
            self.controller.set_source(source)
        self.overlay = GazeOverlay(screen_rect)
        self.preview = GazeCameraPreview()
        self.metrics = GazeMetrics()

        self.controller.point.connect(self.overlay.set_point)
        self.controller.dwell.connect(self.overlay.set_dwell)
        self.controller.dwell.connect(self.preview.set_dwell)
        self.controller.target.connect(self.overlay.set_target)
        self.controller.target.connect(self._on_target)
        self.controller.raw_sample.connect(self.preview.on_sample)
        self.controller.status.connect(self._on_status)
        self.controller.selected.connect(self._on_selected)
        self.controller.exit_progress.connect(self._on_exit_progress)
        self.controller.exit_requested.connect(self.exit_requested)

    @property
    def enabled(self) -> bool:
        return self.controller.running

    def set_enabled(self, enabled: bool) -> None:
        if enabled == self.enabled:
            return
        if not enabled:
            self.controller.stop()
            self.overlay.clear()
            self.overlay.hide()
            self.preview.hide()
            if self._window is not None:
                gaze_style.restore(self._window)
                if self._window_geometry is not None:
                    self._window.setGeometry(self._window_geometry)
                    self._window_geometry = None
            self.status.emit("Hands-free control is off.")
            return
        if self._window is not None:
            gaze_style.apply(self._window, self.palette)
            if self._window.isVisible():
                # Fill the visible screen so the big buttons have room. Set the size directly:
                # maximize/full-screen window states can give the window its own macOS space,
                # which is left behind empty and black when the window is hidden.
                self._window_geometry = self._window.geometry()
                screen = self._window.screen() or QGuiApplication.primaryScreen()
                self._window.setGeometry(screen.availableGeometry())
        started = self.controller.start(self._camera_index, tracker_factory=self._tracker_factory, preview=True)
        if not started:
            # The controller already reported why (a "Camera..." status becomes a problem message).
            if self._window is not None:
                gaze_style.restore(self._window)
                if self._window_geometry is not None:
                    self._window.setGeometry(self._window_geometry)
                    self._window_geometry = None
            return
        self.overlay.show()
        self.preview.place_bottom_right()
        self.preview.show()
        if self._calibrate_on_start and not self.controller.calibration.is_fitted:
            QTimer.singleShot(300, self.recalibrate)  # let the main window paint first

    def toggle_source(self) -> None:
        """Switch between pointing with the head and with the eyes (needs a new calibration)."""
        new = "eyes" if self.controller.source == "head" else "head"
        self.controller.set_source(new)
        self.source_changed.emit(new)
        self.status.emit(f"Now pointing with your {new}. Calibrate to start.")
        if self.enabled and self._calibrate_on_start:
            self.request_recalibrate()

    def request_recalibrate(self) -> None:
        # Run after the current click finishes (a gaze click calls this from inside process()).
        QTimer.singleShot(0, self.recalibrate)

    def recalibrate(self) -> None:
        if not self.enabled:
            self.status.emit("Turn on head movement control first.")
            return
        if self._calibrating:
            return  # one is already open (e.g. the automatic one plus a button press)
        self._calibrating = True
        self.overlay.hide()  # keep the cursor and camera window off the calibration screen
        self.preview.hide()
        try:
            chosen = GazeCalibrationDialog.choose_source(self.controller.source, palette=self.palette)
            if chosen is not None and chosen != self.controller.source:
                self.controller.set_source(chosen)
                self.source_changed.emit(chosen)
            ok = chosen is not None and GazeCalibrationDialog.for_controller(
                self.controller, palette=self.palette
            ).run()
        finally:
            self._calibrating = False
        if not self.enabled:
            return  # gaze was switched off while calibrating
        self.overlay.show()
        self.preview.show()
        if not ok:
            self.problem.emit(CALIBRATION_CANCELLED)  # back to the settings page with a message
            return
        self.metrics.start_task(_now_ms())
        if self.controller.source == "head":
            self.status.emit(
                "Ready. Turn your head toward an option and hold still until the ring fills. "
                "You can also blink slowly once the ring has started."
            )
        else:
            self.status.emit(
                f"Ready (accuracy about {self.controller.error_px:.0f} px). "
                "Look at an option until the ring fills. You can also blink slowly once the ring has started."
            )

    def _alert(self, text: str) -> None:
        self.overlay.set_message(text)
        self.preview.show_error(text)
        QTimer.singleShot(ALERT_MS, lambda: self._clear_alert(text))

    def _clear_alert(self, text: str) -> None:
        if self.overlay.message() == text:
            self.overlay.set_message(None)
            self.preview.show_error(None)

    def _on_status(self, text: str) -> None:
        self.status.emit(text)
        if text.startswith(("Camera", "Gaze tracking stopped")):
            self.problem.emit(text)  # can't continue without a camera
        elif text == STATUS_NO_FACE:
            self._face_missing = True
            QTimer.singleShot(FACE_ALERT_DELAY_MS, self._show_face_alert_if_still_missing)
        elif _is_problem(text):
            self.overlay.set_message(text)
            self.preview.show_error(text)
        elif text == STATUS_TRACKING:
            self._face_missing = False
            self.overlay.set_message(None)
            self.preview.show_error(None)

    def _show_face_alert_if_still_missing(self) -> None:
        if self._face_missing:  # cleared as soon as tracking resumes
            self.overlay.set_message(STATUS_NO_FACE)
            self.preview.show_error(STATUS_NO_FACE)

    def _on_exit_progress(self, progress: float) -> None:
        if progress > 0:
            countdown_s = (EXIT_CLOSE_MS - EXIT_COUNTDOWN_FROM_MS) / 1000
            seconds_left = max(1, math.ceil(countdown_s * (1 - progress)))
            self.overlay.set_message(f"{EXIT_HINT}… {seconds_left}")
        elif self.overlay.message().startswith(EXIT_HINT):
            self.overlay.set_message(None)

    def _on_target(self, _rect) -> None:
        button = self.controller.current_target
        self.preview.set_target_name(button.text() if button is not None else "")
        gaze_style.highlight(button if isinstance(button, QPushButton) else None)

    def _on_selected(self, button: QWidget) -> None:
        text = button.text() if hasattr(button, "text") else ""
        self.metrics.record_selection(_now_ms(), None, text)
        if text == FINISH_BUTTON:
            self.metrics.end_task(_now_ms())
            s = self.metrics.summary()
            seconds = (s["task_ms"] or 0) / 1000
            self.status.emit(f"Booked in {seconds:.0f} s using {s['selections']} selections.")
