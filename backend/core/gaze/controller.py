"""Qt-free GazeController: converts tracker samples into screen coordinates and dwell clicks.

Flow per sample: calibration map -> One-Euro smoothing -> clamp to screen ->
hit-test registered targets -> dwell timer / deliberate blink -> selection callback.
"""

from __future__ import annotations

import math
import threading
from collections.abc import Callable
from dataclasses import dataclass

from backend.core.gaze.calibration import GazeCalibration
from backend.core.gaze.dwell import UNIFORM_DWELL_MS, DwellSelector
from backend.core.gaze.worker import GazeWorker
from backend.core.steadyhand.filter import OneEuroFilter

STATUS_IDLE = "Idle"
STATUS_NO_FACE = "Face not found. Look at the camera."
STATUS_UNCALIBRATED = "Calibrate first"
STATUS_TRACKING = "Tracking"

SNAP_HYSTERESIS_PX = 80

SMOOTH_MIN_CUTOFF = 0.3
SMOOTH_BETA = 0.0005
HEAD_SMOOTH_MIN_CUTOFF = 0.15

HEAD_REST_FRACTION = 0.12

DWELL_GRACE_MS = 400
BLINK_SELECT_MIN_PROGRESS = 0.2
HEAD_CLOSED_EAR = 0.14

EXIT_CLOSE_MS = 5000
EXIT_COUNTDOWN_FROM_MS = 2500

SOURCES = ("head", "eyes")


@dataclass(frozen=True)
class ScreenRect:
    left: int = 0
    top: int = 0
    width: int = 1440
    height: int = 900

    @property
    def right(self) -> int:
        return self.left + self.width

    @property
    def bottom(self) -> int:
        return self.top + self.height

    @property
    def center(self) -> tuple[float, float]:
        return (self.left + self.width / 2.0, self.top + self.height / 2.0)


@dataclass(frozen=True)
class GazeTarget:
    id: str
    x: float
    y: float
    width: float
    height: float
    enabled: bool = True

    def contains(self, px: float, py: float) -> bool:
        return self.x <= px <= self.x + self.width and self.y <= py <= self.y + self.height

    def distance(self, px: float, py: float) -> float:
        dx = max(self.x - px, 0.0, px - (self.x + self.width))
        dy = max(self.y - py, 0.0, py - (self.y + self.height))
        return math.hypot(dx, dy)


class GazeController:
    """Thread-safe gaze/head tracking controller without Qt dependencies."""

    def __init__(
        self,
        screen_rect: ScreenRect | None = None,
        targets_provider: Callable[[], list[GazeTarget]] | None = None,
        on_point: Callable[[tuple[int, int]], None] | None = None,
        on_dwell: Callable[[float], None] | None = None,
        on_selected: Callable[[GazeTarget], None] | None = None,
        on_status: Callable[[str], None] | None = None,
        on_raw_sample: Callable[[dict], None] | None = None,
        on_target: Callable[[GazeTarget | None], None] | None = None,
        on_exit_progress: Callable[[float], None] | None = None,
        on_exit_requested: Callable[[], None] | None = None,
    ):
        self._lock = threading.RLock()
        self._targets_provider = targets_provider
        self._static_targets: list[GazeTarget] = []
        self._on_point = on_point
        self._on_dwell = on_dwell
        self._on_selected = on_selected
        self._on_status = on_status
        self._on_raw_sample = on_raw_sample
        self._on_target = on_target
        self._on_exit_progress = on_exit_progress
        self._on_exit_requested = on_exit_requested

        self.screen_rect = screen_rect or ScreenRect()
        self.source = "head"
        self.calibration = GazeCalibration()
        self.error_px: float | None = None
        self._snap_px = 0.0
        self._target: GazeTarget | None = None
        self.last_blink_ears: list[float] = []
        self.blink_select = True
        self._user_dwell_ms: int | None = None
        self.paused = False
        self._dwell = DwellSelector(grace_ms=DWELL_GRACE_MS)
        self._new_filters()
        self._exit_shown = 0.0
        self._exit_fired = False
        self._closed_at: int | None = None
        self._last_status: str = STATUS_IDLE
        self._worker: GazeWorker | None = None

        # Telemetry snapshot fields
        self._last_point: tuple[int, int] | None = None
        self._last_dwell_progress = 0.0
        self._last_face = False
        self._last_blink = False
        self._last_ear: float | None = None
        self._last_raw: dict | None = None
        self._system_mouse_enabled = False
        self._mouse_controller = None

    @property
    def dwell_ms(self) -> int:
        with self._lock:
            return self._dwell.dwell_ms

    @property
    def running(self) -> bool:
        with self._lock:
            return self._worker is not None and self._worker.running

    @property
    def current_target(self) -> GazeTarget | None:
        with self._lock:
            return self._target

    def set_targets(self, targets: list[GazeTarget]) -> None:
        with self._lock:
            self._static_targets = list(targets)

    def set_screen_rect(self, screen_rect: ScreenRect) -> None:
        with self._lock:
            self.screen_rect = screen_rect

    def set_system_mouse(self, enabled: bool) -> bool:
        with self._lock:
            if not enabled:
                self._system_mouse_enabled = False
                self._mouse_controller = None
                return False
            try:
                from pynput.mouse import Controller

                self._mouse_controller = Controller()
                self._system_mouse_enabled = True
                return True
            except Exception:
                self._mouse_controller = None
                self._system_mouse_enabled = False
                return False

    def set_source(self, source: str) -> None:
        """Point with 'head' or 'eyes'. Switching resets calibration."""
        if source not in SOURCES:
            raise ValueError(f"source must be one of {SOURCES}, got {source!r}")
        with self._lock:
            if source == self.source:
                return
            self.source = source
            self.calibration = GazeCalibration()
            self.error_px = None
            self._snap_px = 0.0
            self._dwell.reset()
            self._new_filters()

    def _new_filters(self) -> None:
        cutoff = HEAD_SMOOTH_MIN_CUTOFF if self.source == "head" else SMOOTH_MIN_CUTOFF
        self._fx = OneEuroFilter(min_cutoff=cutoff, beta=SMOOTH_BETA)
        self._fy = OneEuroFilter(min_cutoff=cutoff, beta=SMOOTH_BETA)

    def _resting(self, pt: tuple[float, float]) -> bool:
        if self.source != "head":
            return False
        r = self.screen_rect
        cx, cy = r.center
        radius = HEAD_REST_FRACTION * min(r.width, r.height)
        return math.hypot(pt[0] - cx, pt[1] - cy) < radius

    def set_dwell_ms(self, ms: int | None) -> None:
        with self._lock:
            self._user_dwell_ms = ms
            self._dwell.dwell_ms = ms if ms is not None else UNIFORM_DWELL_MS

    def set_calibration(self, calibration: GazeCalibration, error_px: float) -> None:
        with self._lock:
            self.calibration = calibration
            self.error_px = float(error_px)
            self._snap_px = float(error_px)
            dwell_ms = self._user_dwell_ms if self._user_dwell_ms is not None else UNIFORM_DWELL_MS
            self._dwell = DwellSelector(dwell_ms, grace_ms=DWELL_GRACE_MS)

    def calibrate_blink(self, ears: list[float]) -> None:
        with self._lock:
            self.last_blink_ears = list(ears)
            tracker = getattr(self._worker, "tracker", None) if self._worker else None
            if tracker is not None and hasattr(tracker, "blink"):
                tracker.blink.calibrate_open(ears)

    def _get_targets(self) -> list[GazeTarget]:
        targets = self._targets_provider() if self._targets_provider is not None else self._static_targets
        return [t for t in targets if t.enabled]

    def _pick_target(self, pt: tuple[float, float]) -> GazeTarget | None:
        targets = self._get_targets()
        if not targets:
            return None
        exact = [t for t in targets if t.contains(pt[0], pt[1])]
        if exact:
            return min(exact, key=lambda t: (t.width * t.height, t.id))
        if self._snap_px <= 0:
            return None
        dist = {t: t.distance(pt[0], pt[1]) for t in targets}
        nearest = min(dist, key=dist.get)
        current = self._target
        if (
            current in dist
            and dist[current] <= self._snap_px
            and dist[current] <= dist[nearest] + SNAP_HYSTERESIS_PX
        ):
            return current
        return nearest if dist[nearest] <= self._snap_px else None

    def _set_target(self, target: GazeTarget | None) -> None:
        self._target = target
        if self._on_target is not None:
            self._on_target(target)

    def _update_exit(self, closed_ms: int) -> None:
        if closed_ms == 0:
            self._exit_fired = False
        progress = min(
            1.0,
            max(0.0, (closed_ms - EXIT_COUNTDOWN_FROM_MS) / (EXIT_CLOSE_MS - EXIT_COUNTDOWN_FROM_MS)),
        )
        if progress != self._exit_shown:
            self._exit_shown = progress
            if self._on_exit_progress is not None:
                self._on_exit_progress(progress)
        if closed_ms >= EXIT_CLOSE_MS and not self._exit_fired:
            self._exit_fired = True
            if self._on_exit_requested is not None:
                self._on_exit_requested()

    def _set_status(self, text: str) -> None:
        if text != self._last_status:
            self._last_status = text
            if self._on_status is not None:
                self._on_status(text)

    def process(self, sample: dict) -> None:
        with self._lock:
            if self.source == "head" and "head" in sample:
                sample = {**sample, "feature": sample["head"]}
            self._last_raw = dict(sample)
            if self._on_raw_sample is not None:
                self._on_raw_sample(sample)
            if self.paused:
                return
            if not self.calibration.is_fitted:
                self._last_face = bool(sample.get("face"))
                self._set_status(STATUS_UNCALIBRATED)
                return
            if not sample.get("face"):
                self._last_face = False
                self._last_blink = False
                self._last_dwell_progress = 0.0
                self._set_status(STATUS_NO_FACE)
                self._dwell.reset()
                if self._on_dwell is not None:
                    self._on_dwell(0.0)
                self._set_target(None)
                self._update_exit(0)
                self._closed_at = None
                return

            self._last_face = True
            self._last_ear = float(sample["ear"]) if "ear" in sample else None
            self._set_status(STATUS_TRACKING)

            closed_ms = int(sample.get("closed_ms", 0))
            if self.source == "head" and float(sample.get("ear", 1.0)) >= HEAD_CLOSED_EAR:
                closed_ms = 0
            self._update_exit(closed_ms)

            eyes_closed = closed_ms > 0
            if eyes_closed:
                if self._closed_at is None:
                    self._closed_at = sample["ts_ms"]
                if self.source == "eyes":
                    return
            elif self._closed_at is not None:
                self._dwell.hold(sample["ts_ms"] - self._closed_at)
                self._closed_at = None

            ts = sample["ts_ms"]
            x, y = self.calibration.map(sample["feature"])
            x = self._fx.filter(x, ts / 1000.0)
            y = self._fy.filter(y, ts / 1000.0)
            r = self.screen_rect
            pt = (
                round(min(max(x, r.left), r.right)),
                round(min(max(y, r.top), r.bottom)),
            )
            self._last_point = pt
            if self._on_point is not None:
                self._on_point(pt)

            if self._system_mouse_enabled and self._mouse_controller is not None:
                try:
                    self._mouse_controller.position = pt
                except Exception:
                    pass

            picked = None if self._resting(pt) else self._pick_target(pt)
            if eyes_closed:
                return

            state = self._dwell.update(picked.id if picked is not None else None, ts)
            active_target = picked if picked is not None and state.target == picked.id else None
            self._set_target(active_target)
            self._last_dwell_progress = state.progress
            if self._on_dwell is not None:
                self._on_dwell(state.progress)

            blinked = (
                self.blink_select
                and bool(sample.get("blink"))
                and state.progress >= BLINK_SELECT_MIN_PROGRESS
            )
            self._last_blink = bool(sample.get("blink"))
            if active_target is not None and (state.fired or blinked):
                self._dwell.consume()
                if self._on_selected is not None:
                    self._on_selected(active_target)

    def snapshot(self) -> dict:
        with self._lock:
            raw = self._last_raw or {}
            feat = raw.get("feature")
            return {
                "running": self.running,
                "source": self.source,
                "status": self._last_status,
                "calibrated": self.calibration.is_fitted,
                "error_px": self.error_px,
                "face_detected": self._last_face,
                "x": self._last_point[0] if self._last_point is not None else None,
                "y": self._last_point[1] if self._last_point is not None else None,
                "raw_feature": [float(feat[0]), float(feat[1])] if feat is not None else None,
                "ear": round(self._last_ear, 4) if self._last_ear is not None else None,
                "dwell_progress": round(self._last_dwell_progress, 3),
                "dwell_ms": self.dwell_ms,
                "blink": self._last_blink,
                "blink_select": self.blink_select,
                "exit_progress": round(self._exit_shown, 3),
                "target_id": self._target.id if self._target is not None else None,
                "lighting_quality": str(raw.get("lighting_quality", "ok")),
                "luma": round(float(raw["luma"]), 1) if "luma" in raw else None,
            }

    def start(
        self,
        camera_index: int = 0,
        tracker_factory: Callable[[], object] | None = None,
        preview: bool = False,
    ) -> bool:
        with self._lock:
            if self.running:
                return True

            if tracker_factory is None:
                from backend.core.gaze.camera_auth import prepare_camera_for_worker
                from backend.core.gaze.tracker import create_tracker

                ok, message = prepare_camera_for_worker(camera_index)
                if not ok:
                    self._set_status(message)
                    return False

                def tracker_factory():
                    return create_tracker(camera_index)

            self._worker = GazeWorker(
                tracker_factory,
                preview=preview,
                on_sample=self.process,
                on_error=self._set_status,
                on_finished=self._clear_worker,
            )
            return self._worker.start()

    def _clear_worker(self) -> None:
        with self._lock:
            self._worker = None

    def stop(self) -> None:
        with self._lock:
            worker = self._worker
        if worker is not None:
            worker.stop()
        self._clear_worker()
        with self._lock:
            self._set_status(STATUS_IDLE)
