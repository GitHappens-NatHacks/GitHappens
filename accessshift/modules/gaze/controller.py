"""GazeController: turns tracker samples into a screen point and button clicks.

Flow per sample: calibration map -> One-Euro smoothing -> clamp to screen ->
hit-test the widget under the point -> dwell timer / deliberate blink -> click().
"""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QObject, QPoint, QRect, QThread, Signal
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QAbstractButton, QApplication, QWidget

from accessshift.modules.gaze.calibration import GazeCalibration
from accessshift.modules.gaze.dwell import DwellSelector, adaptive_dwell_ms
from accessshift.modules.gaze.worker import GazeWorker
from accessshift.modules.steadyhand.filter import OneEuroFilter

STATUS_NO_FACE = "Face not found — look at the camera"
STATUS_UNCALIBRATED = "Calibrate first"
STATUS_TRACKING = "Gaze tracking"


def _button_at(widget: QWidget | None) -> QAbstractButton | None:
    """The enabled, visible button under the gaze (or containing the widget there)."""
    while widget is not None and not isinstance(widget, QAbstractButton):
        widget = widget.parentWidget()
    if widget is not None and widget.isEnabled() and widget.isVisible():
        return widget
    return None


class GazeController(QObject):
    point = Signal(QPoint)  # smoothed gaze point, global screen coordinates
    dwell = Signal(float)  # 0..1 progress on the current button
    selected = Signal(QWidget)  # a button was clicked by gaze
    status = Signal(str)
    raw_sample = Signal(dict)  # every tracker sample (used by the calibration dialog)

    def __init__(
        self,
        hit_test: Callable[[QPoint], QWidget | None] | None = None,
        screen_rect: QRect | None = None,
        parent: QObject | None = None,
    ):
        super().__init__(parent)
        self._hit_test = hit_test or QApplication.widgetAt
        if screen_rect is None:
            screen = QGuiApplication.primaryScreen()
            screen_rect = screen.geometry() if screen else QRect(0, 0, 1440, 900)
        self.screen_rect = screen_rect
        self.calibration = GazeCalibration()
        self.error_px: float | None = None
        self.paused = False  # True while calibrating: report samples, click nothing
        self._dwell = DwellSelector()
        self._fx = OneEuroFilter(min_cutoff=1.0, beta=0.01)
        self._fy = OneEuroFilter(min_cutoff=1.0, beta=0.01)
        self._last_status: str | None = None
        self._thread: QThread | None = None
        self._worker: GazeWorker | None = None

    # --- configuration -------------------------------------------------------------
    @property
    def dwell_ms(self) -> int:
        return self._dwell.dwell_ms

    def set_calibration(self, calibration: GazeCalibration, error_px: float) -> None:
        self.calibration = calibration
        self.error_px = error_px
        self._dwell = DwellSelector(adaptive_dwell_ms(error_px))

    # --- per-sample logic (testable without a camera) ------------------------------
    def _set_status(self, text: str) -> None:
        if text != self._last_status:
            self._last_status = text
            self.status.emit(text)

    def process(self, sample: dict) -> None:
        self.raw_sample.emit(sample)
        if self.paused:
            return
        if not self.calibration.is_fitted:
            self._set_status(STATUS_UNCALIBRATED)
            return
        if not sample.get("face"):
            self._set_status(STATUS_NO_FACE)
            self._dwell.update(None, sample.get("ts_ms", 0))
            self.dwell.emit(0.0)
            return
        self._set_status(STATUS_TRACKING)

        ts = sample["ts_ms"]
        x, y = self.calibration.map(sample["feature"])
        x, y = self._fx.filter(x, ts / 1000.0), self._fy.filter(y, ts / 1000.0)
        r = self.screen_rect
        pt = QPoint(
            int(min(max(x, r.left()), r.right())),
            int(min(max(y, r.top()), r.bottom())),
        )
        self.point.emit(pt)

        button = _button_at(self._hit_test(pt))
        state = self._dwell.update(button, ts)
        self.dwell.emit(state.progress)
        if button is not None and (state.fired or sample.get("blink")):
            self._dwell.consume()  # not reset(): staring after a click must not click again
            button.click()
            self.selected.emit(button)

    # --- camera thread ---------------------------------------------------------------
    @property
    def running(self) -> bool:
        return self._thread is not None

    def start(self, camera_index: int = 0, tracker_factory: Callable[[], object] | None = None) -> None:
        if self.running:
            return
        if tracker_factory is None:
            from accessshift.modules.gaze.tracker import GazeTracker  # heavy import: camera + mediapipe

            def tracker_factory():
                return GazeTracker(camera_index)

        self._thread = QThread()
        self._worker = GazeWorker(tracker_factory)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.sample.connect(self.process)  # queued: process() runs on the UI thread
        self._worker.error.connect(self._set_status)
        self._worker.finished.connect(self._thread.quit)
        self._thread.start()

    def stop(self) -> None:
        if not self.running:
            return
        self._worker.stop()
        self._thread.quit()
        self._thread.wait(3000)
        self._thread = None
        self._worker = None
