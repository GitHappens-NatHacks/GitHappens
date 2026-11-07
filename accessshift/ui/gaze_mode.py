"""GazeMode: everything the main window needs to turn GazeControl on and off.

Owns the GazeController (camera thread), the gaze cursor overlay and the pitch
metrics, so the main window only calls set_enabled() / recalibrate().
"""

from __future__ import annotations

import os
import time
from collections.abc import Callable

from PySide6.QtCore import QObject, QRect, QTimer, Signal
from PySide6.QtWidgets import QWidget

from accessshift.modules.gaze.controller import GazeController
from accessshift.modules.gaze.metrics import GazeMetrics
from accessshift.ui.gaze_calibration_dialog import GazeCalibrationDialog
from accessshift.ui.gaze_overlay import GazeOverlay

FINISH_BUTTON = "Book appointment"  # selecting this ends the timed booking task


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
        self.controller = GazeController(screen_rect=screen_rect, parent=self)
        self.overlay = GazeOverlay(screen_rect)
        self.metrics = GazeMetrics()

        self.controller.point.connect(self.overlay.set_point)
        self.controller.dwell.connect(self.overlay.set_dwell)
        self.controller.target.connect(self.overlay.set_target)
        self.controller.status.connect(lambda text: self.status.emit(f"Gaze: {text}"))
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
            self.status.emit("Gaze: off")
            return
        self.controller.start(self._camera_index, tracker_factory=self._tracker_factory)
        self.overlay.show()
        if self._calibrate_on_start and not self.controller.calibration.is_fitted:
            QTimer.singleShot(300, self.recalibrate)  # let the main window paint first

    def recalibrate(self) -> None:
        if not self.enabled:
            self.status.emit("Gaze: turn on GazeControl first")
            return
        self.overlay.hide()  # keep the cursor off the calibration screen
        ok = GazeCalibrationDialog(self.controller).run()
        self.overlay.show()
        if not ok:
            self.status.emit("Gaze: calibration cancelled")
            return
        self.metrics.start_task(_now_ms())
        self.status.emit(
            f"Gaze ready: accuracy ±{self.controller.error_px:.0f} px, dwell {self.controller.dwell_ms} ms. "
            "Look at a button until the ring fills, or slow-blink."
        )

    def _on_selected(self, button: QWidget) -> None:
        text = button.text() if hasattr(button, "text") else ""
        self.metrics.record_selection(_now_ms(), None, text)
        if text == FINISH_BUTTON:
            self.metrics.end_task(_now_ms())
            s = self.metrics.summary()
            seconds = (s["task_ms"] or 0) / 1000
            self.status.emit(f"Gaze: booked in {seconds:.0f} s using {s['selections']} gaze selections")
