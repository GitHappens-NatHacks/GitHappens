"""GazeMode: everything the main window needs to turn GazeControl on and off.

Owns the GazeController (camera thread), the gaze cursor overlay, the camera
preview, the big high-contrast button style and the pitch metrics, so the main
window only calls set_enabled() / recalibrate(). Turning it off restores the
window exactly as it was.
"""

from __future__ import annotations

import os
import time
from collections.abc import Callable

from PySide6.QtCore import QObject, QRect, QTimer, Signal
from PySide6.QtWidgets import QPushButton, QWidget

from accessshift.modules.gaze.controller import STATUS_NO_FACE, STATUS_TRACKING, GazeController
from accessshift.modules.gaze.metrics import GazeMetrics
from accessshift.ui import gaze_style
from accessshift.ui.gaze_calibration_dialog import GazeCalibrationDialog
from accessshift.ui.gaze_camera_preview import GazeCameraPreview
from accessshift.ui.gaze_overlay import GazeOverlay

FINISH_BUTTON = "Book appointment"  # selecting this ends the timed booking task
ALERT_MS = 3000  # how long one-off alerts (e.g. calibration cancelled) stay up


def _is_problem(status: str) -> bool:
    return status == STATUS_NO_FACE or status.startswith(("Camera", "Gaze tracking stopped"))


def _now_ms() -> int:
    return int(time.monotonic() * 1000)


class GazeMode(QObject):
    status = Signal(str)

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
        self._window = parent if isinstance(parent, QWidget) else None  # gets the big-button style
        self.controller = GazeController(screen_rect=screen_rect, parent=self)
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
            self.status.emit("Gaze: off")
            return
        if self._window is not None:
            gaze_style.apply(self._window)
        self.controller.start(self._camera_index, tracker_factory=self._tracker_factory, preview=True)
        self.overlay.show()
        self.preview.place_bottom_right()
        self.preview.show()
        if self._calibrate_on_start and not self.controller.calibration.is_fitted:
            QTimer.singleShot(300, self.recalibrate)  # let the main window paint first

    def recalibrate(self) -> None:
        if not self.enabled:
            self.status.emit("Gaze: turn on GazeControl first")
            return
        self.overlay.hide()  # keep the cursor and camera window off the calibration screen
        self.preview.hide()
        ok = GazeCalibrationDialog(self.controller).run()
        self.overlay.show()
        self.preview.show()
        if not ok:
            self.status.emit("Gaze: calibration cancelled")
            self._alert("Calibration cancelled. Press Recalibrate gaze to try again")
            return
        self.metrics.start_task(_now_ms())
        self.status.emit(
            f"Gaze ready: accuracy ±{self.controller.error_px:.0f} px, dwell {self.controller.dwell_ms} ms. "
            "Look at a button until the ring fills, or slow-blink."
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
        self.status.emit(f"Gaze: {text}")
        if _is_problem(text):
            self.overlay.set_message(text)
            self.preview.show_error(text)
        elif text == STATUS_TRACKING:
            self.overlay.set_message(None)
            self.preview.show_error(None)

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
            self.status.emit(f"Gaze: booked in {seconds:.0f} s using {s['selections']} gaze selections")
