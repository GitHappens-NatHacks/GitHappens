"""Map eye-relative gaze features to screen pixels.

The user looks at known dots; we fit an affine map per screen axis
(terms 1, u, v) with least squares. Pure math: NumPy only.

Why affine and not a quadratic: webcam eye features are small and noisy. A 6-term
quadratic on 7-9 dots bends to fit the noise and can predict thousands of pixels
off screen (seen in real runs). Three terms can't overfit that way.
"""

from __future__ import annotations

import numpy as np

Point = tuple[float, float]

# 3x3 grid in normalized screen coordinates, row by row (top row first).
CALIBRATION_POINTS: list[Point] = [(x, y) for y in (0.1, 0.5, 0.9) for x in (0.1, 0.5, 0.9)]

_MIN_POINTS = 3  # one per term


def _terms(features: list[Point]) -> np.ndarray:
    f = np.asarray(features, dtype=float)
    u, v = f[:, 0], f[:, 1]
    return np.column_stack([np.ones_like(u), u, v])


class GazeCalibration:
    def __init__(self) -> None:
        self._coef: np.ndarray | None = None  # shape (3, 2): one column per screen axis

    @property
    def is_fitted(self) -> bool:
        return self._coef is not None

    def fit(self, features: list[Point], targets: list[Point]) -> None:
        if len(features) != len(targets):
            raise ValueError(f"{len(features)} features but {len(targets)} targets")
        if len(features) < _MIN_POINTS:
            raise ValueError(f"need at least {_MIN_POINTS} calibration points, got {len(features)}")
        self._coef, *_ = np.linalg.lstsq(_terms(features), np.asarray(targets, dtype=float), rcond=None)

    def map(self, feature: Point) -> Point:
        if self._coef is None:
            raise RuntimeError("GazeCalibration.map called before fit")
        x, y = (_terms([feature]) @ self._coef)[0]
        return (float(x), float(y))

    def error_px(self, features: list[Point], targets: list[Point]) -> float:
        if self._coef is None:
            raise RuntimeError("GazeCalibration.error_px called before fit")
        predicted = _terms(features) @ self._coef
        return float(np.mean(np.linalg.norm(predicted - np.asarray(targets, dtype=float), axis=1)))


# --- head pointing: guided poses instead of dots ---------------------------------------
# The user faces forward, then turns left/right and tilts up/down as far as is comfortable.
# Direction comes from what they actually did, so "up" is always up whatever the camera's
# mirroring; their comfortable range spans HEAD_REACH of the screen (small wobbles barely move).
HEAD_POSES = ("center", "left", "right", "up", "down")
HEAD_REACH = 0.8
HEAD_MIN_RANGE = 0.04  # head-feature units; less than this means the user barely moved


def head_calibration(poses: dict[str, Point], size: tuple[float, float]) -> GazeCalibration:
    """Axis-aligned map from head poses: centre -> screen centre, comfortable range -> HEAD_REACH."""
    w, h = size
    nx, ny = poses["center"]
    span_x = poses["right"][0] - poses["left"][0]
    span_y = poses["down"][1] - poses["up"][1]
    if abs(span_x) < HEAD_MIN_RANGE:
        raise ValueError("Turn your head further left and right")
    if abs(span_y) < HEAD_MIN_RANGE:
        raise ValueError("Tilt your head further up and down")
    gx = HEAD_REACH * w / span_x  # sign follows the user's movement, so left/right never flip
    gy = HEAD_REACH * h / span_y
    c = GazeCalibration()
    c._coef = np.array([[w / 2 - nx * gx, h / 2 - ny * gy], [gx, 0.0], [0.0, gy]])
    return c


class DotCollector:
    """Collects one steady gaze feature per calibration dot.

    For each dot: wait settle_ms for the eyes to land, then gather collect_ms of
    open-eye samples. Too few samples, or samples that spread more than max_spread
    (eyes still moving), and the same dot is repeated.
    """

    def __init__(
        self,
        points: list[Point],
        size: tuple[float, float],
        settle_ms: int = 500,
        collect_ms: int = 1000,
        min_samples: int = 5,
        max_spread: float = 0.01,
    ):
        self.points, self.size = points, size
        self.settle_ms, self.collect_ms = settle_ms, collect_ms
        self.min_samples, self.max_spread = min_samples, max_spread
        self.index = 0
        self.retries = 0
        self.features: list[Point] = []
        self.ears: list[float] = []  # open-eye EAR samples, for BlinkDetector.calibrate_open
        self.debug: list[dict] = []  # per-dot sample count, spread, retries
        self._started: int | None = None
        self._samples: list[Point] = []

    @property
    def done(self) -> bool:
        return self.index >= len(self.points)

    def target_px(self, i: int | None = None) -> Point:
        x, y = self.points[self.index if i is None else i]
        return (x * self.size[0], y * self.size[1])

    def targets_px(self) -> list[Point]:
        return [self.target_px(i) for i in range(len(self.points))]

    def progress(self, ts_ms: int) -> float:
        """0..1 through the collecting part of the current dot (for drawing)."""
        if self._started is None:
            return 0.0
        return min(1.0, max(0.0, (ts_ms - self._started - self.settle_ms) / self.collect_ms))

    def update(self, sample: dict, ear_threshold: float) -> None:
        if self.done:
            return
        ts = sample["ts_ms"]
        if self._started is None:
            self._started = ts
        elapsed = ts - self._started
        if elapsed >= self.settle_ms and sample.get("face") and sample["ear"] >= ear_threshold:
            self._samples.append(tuple(sample["feature"]))
            self.ears.append(sample["ear"])
        if elapsed < self.settle_ms + self.collect_ms:
            return

        us = [p[0] for p in self._samples]
        vs = [p[1] for p in self._samples]
        steady = len(self._samples) >= self.min_samples and max(np.std(us), np.std(vs)) <= self.max_spread
        if steady:
            self.features.append((float(np.median(us)), float(np.median(vs))))
            self.debug.append({
                "target_norm": self.points[self.index],
                "samples": len(self._samples),
                "std_u": float(np.std(us)),
                "std_v": float(np.std(vs)),
                "retries": self.retries,
            })
            self.index += 1
            self.retries = 0
        else:
            self.retries += 1
        self._started, self._samples = None, []
