"""GazeController: turns tracker samples into a screen point and button clicks.

Flow per sample: calibration map -> One-Euro smoothing -> clamp to screen ->
hit-test the widget under the point -> dwell timer / deliberate blink -> click().
"""

from __future__ import annotations

import math
from collections.abc import Callable

from PySide6.QtCore import QObject, QPoint, QRect, QThread, Signal
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QAbstractButton, QApplication, QWidget
from shiboken6 import isValid

from accessshift.modules.gaze.calibration import GazeCalibration
from accessshift.modules.gaze.dwell import UNIFORM_DWELL_MS, DwellSelector
from accessshift.modules.gaze.worker import GazeWorker
from accessshift.modules.steadyhand.filter import OneEuroFilter

STATUS_NO_FACE = "Face not found. Look at the camera."
STATUS_UNCALIBRATED = "Calibrate first"
STATUS_TRACKING = "Tracking"

# Keep the current target unless another button is at least this much nearer (stops flicker).
SNAP_HYSTERESIS_PX = 80

# Gaze smoothing (One-Euro). Low beta: webcam jitter looks like fast motion, so a high
# beta would switch smoothing off. Measured: 18 px -> 8 px jitter, 300 px move in ~0.26 s.
SMOOTH_MIN_CUTOFF = 0.3
SMOOTH_BETA = 0.0005
HEAD_SMOOTH_MIN_CUTOFF = 0.15  # head mode: slower, calmer dot

# Head mode: facing forward (dot near the screen centre) is "resting" and selects nothing,
# so you only select by clearly turning toward a square. Radius as a fraction of screen size.
HEAD_REST_FRACTION = 0.12

DWELL_GRACE_MS = 400  # a glance away shorter than this keeps the dwell ring going
# Blink may finish a selection only after the dwell ring has clearly started.
BLINK_SELECT_MIN_PROGRESS = 0.2
# Head tilt (looking up) often lowers EAR without a real eye close. Below this it counts as closed.
HEAD_CLOSED_EAR = 0.14

# Close your eyes this long to exit gaze control (no aiming needed). Longer than
# a select blink, and longer than a brief low-EAR dip when tilting the head up.
EXIT_CLOSE_MS = 5000
EXIT_COUNTDOWN_FROM_MS = 2500

# What moves the pointer. Head is the default: turning the head is a much bigger,
# steadier webcam signal than iris movement. Eyes is for people who can't move their head.
SOURCES = ("head", "eyes")

# Windows with this property set (the gaze cursor overlay) are invisible to gaze clicks.
GAZE_IGNORE = "gaze_ignore"


def widget_under(pt: QPoint) -> QWidget | None:
    """Widget at a global screen point, skipping gaze-ignored windows like the overlay."""
    w = QApplication.widgetAt(pt)
    if w is not None and not w.window().property(GAZE_IGNORE):
        return w
    candidates = [
        t for t in QApplication.topLevelWidgets()
        if t.isVisible() and not t.property(GAZE_IGNORE) and t.frameGeometry().contains(pt)
    ]
    if not candidates:
        return None
    active = QApplication.activeWindow()
    top = active if active in candidates else candidates[-1]
    return top.childAt(top.mapFromGlobal(pt)) or top


def _button_at(widget: QWidget | None) -> QAbstractButton | None:
    """The enabled, visible button under the gaze (or containing the widget there)."""
    while widget is not None and not isinstance(widget, QAbstractButton):
        widget = widget.parentWidget()
    if widget is not None and widget.isEnabled() and widget.isVisible():
        return widget
    return None


def visible_buttons() -> list[QAbstractButton]:
    """Every enabled, visible button in the app's windows (gaze-ignored windows excluded)."""
    out: list[QAbstractButton] = []
    for top in QApplication.topLevelWidgets():
        if not top.isVisible() or top.property(GAZE_IGNORE):
            continue
        found = top.findChildren(QAbstractButton)
        if isinstance(top, QAbstractButton):
            found.append(top)
        out += [b for b in found if b.isVisible() and b.isEnabled()]
    return out


def _alive(w: QWidget | None) -> QWidget | None:
    """The widget, or None if Qt already deleted it (e.g. a closed popup's button)."""
    return w if w is not None and isValid(w) else None


def _global_rect(w: QWidget) -> QRect:
    """Button bounds in global screen coords (recomputed each frame for layout shifts)."""
    top_left = w.mapToGlobal(QPoint(0, 0))
    return QRect(top_left.x(), top_left.y(), w.width(), w.height())


def _distance(pt: QPoint, r: QRect) -> float:
    dx = max(r.left() - pt.x(), 0, pt.x() - r.right())
    dy = max(r.top() - pt.y(), 0, pt.y() - r.bottom())
    return math.hypot(dx, dy)


class GazeController(QObject):
    point = Signal(QPoint)  # smoothed gaze point, global screen coordinates
    dwell = Signal(float)  # 0..1 progress on the current button
    selected = Signal(QWidget)  # a button was clicked by gaze
    status = Signal(str)
    raw_sample = Signal(dict)  # every tracker sample (used by the calibration dialog)
    target = Signal(QRect)  # global rect of the targeted button, or an empty QRect
    exit_progress = Signal(float)  # 0..1 while eyes are held closed to exit
    exit_requested = Signal()  # eyes held closed for EXIT_CLOSE_MS

    def __init__(
        self,
        hit_test: Callable[[QPoint], QWidget | None] | None = None,
        screen_rect: QRect | None = None,
        parent: QObject | None = None,
        buttons: Callable[[], list[QAbstractButton]] | None = None,
    ):
        super().__init__(parent)
        self._hit_test = hit_test or widget_under
        self._buttons = buttons or visible_buttons
        self._snap_px = 0.0  # 0 = only exact hits; set to gaze accuracy by set_calibration()
        self._target: QAbstractButton | None = None
        if screen_rect is None:
            screen = QGuiApplication.primaryScreen()
            screen_rect = screen.geometry() if screen else QRect(0, 0, 1440, 900)
        self.screen_rect = screen_rect
        self.source = "head"
        self.calibration = GazeCalibration()
        self.error_px: float | None = None
        self.last_blink_ears: list[float] = []
        self.blink_select = True  # a slow blink confirms (user setting)
        self._user_dwell_ms: int | None = None  # user setting; None = automatic from accuracy
        self.paused = False  # True while calibrating: report samples, click nothing
        self._dwell = DwellSelector(grace_ms=DWELL_GRACE_MS)
        self._new_filters()
        self._exit_shown = 0.0
        self._exit_fired = False
        self._closed_at: int | None = None  # when the eyes closed (dwell is paused meanwhile)
        self._last_status: str | None = None
        self._thread: QThread | None = None
        self._worker: GazeWorker | None = None

    # --- configuration -------------------------------------------------------------
    @property
    def dwell_ms(self) -> int:
        return self._dwell.dwell_ms

    def set_source(self, source: str) -> None:
        """Point with "head" or "eyes". Switching needs a new calibration."""
        if source not in SOURCES:
            raise ValueError(f"source must be one of {SOURCES}, got {source!r}")
        if source == self.source:
            return
        self.source = source
        self.calibration = GazeCalibration()
        self.error_px = None
        self._dwell.reset()
        self._new_filters()

    def _new_filters(self) -> None:
        cutoff = HEAD_SMOOTH_MIN_CUTOFF if self.source == "head" else SMOOTH_MIN_CUTOFF
        self._fx = OneEuroFilter(min_cutoff=cutoff, beta=SMOOTH_BETA)
        self._fy = OneEuroFilter(min_cutoff=cutoff, beta=SMOOTH_BETA)

    def _resting(self, pt: QPoint) -> bool:
        if self.source != "head":
            return False
        r = self.screen_rect
        radius = HEAD_REST_FRACTION * min(r.width(), r.height())
        return math.hypot(pt.x() - r.center().x(), pt.y() - r.center().y()) < radius

    def set_dwell_ms(self, ms: int | None) -> None:
        """Use the person's chosen selection speed (None = the default dwell)."""
        self._user_dwell_ms = ms
        self._dwell.dwell_ms = ms if ms is not None else UNIFORM_DWELL_MS

    def set_calibration(self, calibration: GazeCalibration, error_px: float) -> None:
        self.calibration = calibration
        self.error_px = error_px
        self._snap_px = error_px
        # Same dwell for every button (the person's chosen speed). Accuracy only sets the snap radius.
        dwell_ms = self._user_dwell_ms if self._user_dwell_ms is not None else UNIFORM_DWELL_MS
        self._dwell = DwellSelector(dwell_ms, grace_ms=DWELL_GRACE_MS)

    def calibrate_blink(self, ears: list[float]) -> None:
        """Tune the blink threshold to this user's open-eye EAR (from calibration)."""
        self.last_blink_ears = list(ears)
        tracker = getattr(self._worker, "tracker", None)
        if tracker is not None:
            tracker.blink.calibrate_open(ears)

    # --- per-sample logic (testable without a camera) ------------------------------
    def _pick_button(self, pt: QPoint) -> QAbstractButton | None:
        """Button exactly under the gaze, else the nearest one within gaze accuracy.

        While a popup (modal dialog) is open, only its own buttons can be chosen, so gaze
        never presses something hidden behind it (e.g. "Back" behind the booked popup).
        """
        popup = QApplication.activeModalWidget()
        if popup is not None and popup.property(GAZE_IGNORE):
            popup = None

        def allowed(b: QAbstractButton | None) -> bool:
            return b is not None and (popup is None or b is popup or popup.isAncestorOf(b))

        exact = _button_at(self._hit_test(pt))
        if not allowed(exact):
            exact = None
        if exact is not None or self._snap_px <= 0:
            return exact
        dist = {b: _distance(pt, _global_rect(b)) for b in self._buttons() if allowed(b)}
        if not dist:
            return None
        nearest = min(dist, key=dist.get)
        current = _alive(self._target)
        if current in dist and dist[current] <= self._snap_px and dist[current] <= dist[nearest] + SNAP_HYSTERESIS_PX:
            return current
        return nearest if dist[nearest] <= self._snap_px else None

    def _set_target(self, button: QAbstractButton | None) -> None:
        # Always re-emit the live rect so the outline tracks layout/resize changes.
        button = _alive(button)
        self._target = button
        self.target.emit(_global_rect(button) if button is not None else QRect())

    def _update_exit(self, closed_ms: int) -> None:
        if closed_ms == 0:
            self._exit_fired = False
        progress = min(1.0, max(0.0, (closed_ms - EXIT_COUNTDOWN_FROM_MS) / (EXIT_CLOSE_MS - EXIT_COUNTDOWN_FROM_MS)))
        if progress != self._exit_shown:
            self._exit_shown = progress
            self.exit_progress.emit(progress)
        if closed_ms >= EXIT_CLOSE_MS and not self._exit_fired:
            self._exit_fired = True
            self.exit_requested.emit()

    def _set_status(self, text: str) -> None:
        if text != self._last_status:
            self._last_status = text
            self.status.emit(text)

    def process(self, sample: dict) -> None:
        if self.source == "head" and "head" in sample:
            sample = {**sample, "feature": sample["head"]}  # calibration and mapping use the active source
        self.raw_sample.emit(sample)
        if self.paused:
            return
        if not self.calibration.is_fitted:
            self._set_status(STATUS_UNCALIBRATED)
            return
        if not sample.get("face"):
            self._set_status(STATUS_NO_FACE)
            self._dwell.reset()
            self.dwell.emit(0.0)
            self._set_target(None)
            self._update_exit(0)
            self._closed_at = None
            return
        self._set_status(STATUS_TRACKING)

        closed_ms = sample.get("closed_ms", 0)
        if self.source == "head" and float(sample.get("ear", 1.0)) >= HEAD_CLOSED_EAR:
            closed_ms = 0  # a mild dip from tilting the head is not closed eyes
        self._update_exit(closed_ms)
        # While the eyes are shut the dwell pauses, so closing your eyes (a blink, or to exit)
        # never clicks anything. Eye features are garbage then, so eyes mode also freezes the
        # dot; head pointing stays valid, so in head mode the dot keeps following your head.
        eyes_closed = closed_ms > 0
        if eyes_closed:
            if self._closed_at is None:
                self._closed_at = sample["ts_ms"]
            if self.source == "eyes":
                return
        elif self._closed_at is not None:
            self._dwell.hold(sample["ts_ms"] - self._closed_at)  # closed time doesn't count
            self._closed_at = None

        ts = sample["ts_ms"]
        x, y = self.calibration.map(sample["feature"])
        x, y = self._fx.filter(x, ts / 1000.0), self._fy.filter(y, ts / 1000.0)
        r = self.screen_rect
        pt = QPoint(
            round(min(max(x, r.left()), r.right())),
            round(min(max(y, r.top()), r.bottom())),
        )
        self.point.emit(pt)

        picked = None if self._resting(pt) else self._pick_button(pt)
        if eyes_closed:  # head mode: move the dot, keep the highlight, but don't count or click
            return
        state = self._dwell.update(picked, ts)
        button = _alive(state.target)  # may stay on the previous button during a brief glance away
        if button is None and state.target is not None:
            self._dwell.reset()  # that button was deleted (e.g. its popup closed)
        self._set_target(button)
        self.dwell.emit(state.progress)
        blinked = (
            self.blink_select
            and bool(sample.get("blink"))
            and state.progress >= BLINK_SELECT_MIN_PROGRESS
        )
        if button is not None and (state.fired or blinked):
            self._dwell.consume()  # not reset(): staring after a click must not click again
            button.click()
            self.selected.emit(button)

    # --- camera thread ---------------------------------------------------------------
    @property
    def running(self) -> bool:
        return self._thread is not None

    @property
    def current_target(self) -> QAbstractButton | None:
        return _alive(self._target)

    def start(
        self,
        camera_index: int = 0,
        tracker_factory: Callable[[], object] | None = None,
        preview: bool = False,
    ) -> bool:
        if self.running:
            return True

        if tracker_factory is None:
            # macOS: authorize on this UI thread before the worker opens the camera.
            from accessshift.modules.gaze.camera_auth import prepare_camera_for_worker
            from accessshift.modules.gaze.tracker import create_tracker  # mediapipe / eyetrax / hybrid

            ok, message = prepare_camera_for_worker(camera_index)
            if not ok:
                self._set_status(message)
                return False

            def tracker_factory():
                return create_tracker(camera_index)

        self._thread = QThread()
        self._worker = GazeWorker(tracker_factory, preview=preview)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.sample.connect(self.process)  # queued: process() runs on the UI thread
        self._worker.error.connect(self._set_status)
        self._worker.finished.connect(self._thread.quit)
        self._thread.finished.connect(self._clear_worker)
        self._thread.start()
        return True

    def _clear_worker(self) -> None:
        self._thread = None
        self._worker = None

    def stop(self) -> None:
        if not self.running:
            return
        worker = self._worker
        thread = self._thread
        if worker is not None:
            worker.stop()
        if thread is not None:
            thread.quit()
            thread.wait(3000)
        self._clear_worker()
