"""Map eye-relative gaze features to screen pixels.

The user looks at known dots; we fit an affine map per screen axis
(terms 1, u, v) with least squares. Features are standardized before the fit
so a weak vertical signal does not blow up the coefficients.
"""

from __future__ import annotations

import numpy as np

Point = tuple[float, float]

# 3x3 grid in normalized screen coordinates, row by row (top row first).
CALIBRATION_POINTS: list[Point] = [(x, y) for y in (0.1, 0.5, 0.9) for x in (0.1, 0.5, 0.9)]

_MIN_POINTS = 3  # one per term
_MIN_STD = 1e-4


def _terms(features: np.ndarray) -> np.ndarray:
    u, v = features[:, 0], features[:, 1]
    return np.column_stack([np.ones_like(u), u, v])


class GazeCalibration:
    def __init__(self) -> None:
        self._coef: np.ndarray | None = None  # shape (3, 2): one column per screen axis
        self._mean = np.zeros(2)
        self._std = np.ones(2)

    @property
    def is_fitted(self) -> bool:
        return self._coef is not None

    def _normalize(self, features: np.ndarray) -> np.ndarray:
        return (features - self._mean) / self._std

    def fit(self, features: list[Point], targets: list[Point]) -> None:
        if len(features) != len(targets):
            raise ValueError(f"{len(features)} features but {len(targets)} targets")
        if len(features) < _MIN_POINTS:
            raise ValueError(f"need at least {_MIN_POINTS} calibration points, got {len(features)}")

        feat = np.asarray(features, dtype=float)
        targ = np.asarray(targets, dtype=float)
        self._mean = feat.mean(axis=0)
        std = feat.std(axis=0)
        # Keep a usable scale when one axis barely moved during calibration.
        self._std = np.where(std < _MIN_STD, 1.0, std)
        normalized = self._normalize(feat)
        self._coef, *_ = np.linalg.lstsq(_terms(normalized), targ, rcond=None)

        # Drop at most one gross outlier and refit. One bad blink can otherwise
        # pull the whole affine map off by hundreds of pixels.
        if len(features) >= 6 and self._coef is not None:
            predicted = _terms(normalized) @ self._coef
            residuals = np.linalg.norm(predicted - targ, axis=1)
            worst = int(np.argmax(residuals))
            med = float(np.median(residuals))
            if residuals[worst] > max(3.0 * med, 120.0):
                keep = np.ones(len(features), dtype=bool)
                keep[worst] = False
                feat_k = feat[keep]
                targ_k = targ[keep]
                self._mean = feat_k.mean(axis=0)
                std_k = feat_k.std(axis=0)
                self._std = np.where(std_k < _MIN_STD, 1.0, std_k)
                normalized_k = self._normalize(feat_k)
                self._coef, *_ = np.linalg.lstsq(_terms(normalized_k), targ_k, rcond=None)

    def map(self, feature: Point) -> Point:
        if self._coef is None:
            raise RuntimeError("GazeCalibration.map called before fit")
        normalized = self._normalize(np.asarray([feature], dtype=float))
        x, y = (_terms(normalized) @ self._coef)[0]
        return (float(x), float(y))

    def error_px(self, features: list[Point], targets: list[Point]) -> float:
        if self._coef is None:
            raise RuntimeError("GazeCalibration.error_px called before fit")
        predicted = np.asarray([self.map(f) for f in features], dtype=float)
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
    open-eye samples. Prefer a low-spread window. After max_retries, accept the
    best available window so one shaky glance does not loop forever.
    """

    def __init__(
        self,
        points: list[Point],
        size: tuple[float, float],
        settle_ms: int = 800,
        collect_ms: int = 1600,
        min_samples: int = 5,
        max_spread: float = 0.04,
        max_retries: int = 3,
        force_min_samples: int = 3,
    ):
        self.points, self.size = points, size
        self.settle_ms, self.collect_ms = settle_ms, collect_ms
        self.min_samples, self.max_spread = min_samples, max_spread
        self.max_retries = max_retries
        self.force_min_samples = force_min_samples
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

    def _window_stats(self, chunk: list[Point]) -> tuple[Point, float, float]:
        us = [p[0] for p in chunk]
        vs = [p[1] for p in chunk]
        return (
            (float(np.median(us)), float(np.median(vs))),
            float(np.std(us)),
            float(np.std(vs)),
        )

    def _best_window(self) -> tuple[Point | None, int, float, float]:
        """Steadiest contiguous window. Returns (median, n, std_u, std_v)."""
        n = len(self._samples)
        if n < self.force_min_samples:
            return (None, n, 0.0, 0.0)
        window = max(self.min_samples, min(n, max(self.min_samples, n // 2)))
        if n < window:
            window = n
        best_med: Point | None = None
        best_n = 0
        best_su = 0.0
        best_sv = 0.0
        best_spread = float("inf")
        for start in range(0, n - window + 1):
            med, su, sv = self._window_stats(self._samples[start : start + window])
            spread = max(su, sv)
            if spread < best_spread:
                best_spread = spread
                best_med, best_n, best_su, best_sv = med, window, su, sv
        return (best_med, best_n, best_su, best_sv)

    def _accept(self, feature: Point, n: int, std_u: float, std_v: float) -> None:
        self.features.append(feature)
        self.debug.append({
            "target_norm": self.points[self.index],
            "samples": n,
            "std_u": std_u,
            "std_v": std_v,
            "retries": self.retries,
        })
        self.index += 1
        self.retries = 0

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

        med, n, su, sv = self._best_window()
        spread = max(su, sv)
        steady = med is not None and n >= self.min_samples and spread <= self.max_spread
        force = (
            med is not None
            and n >= self.force_min_samples
            and self.retries >= self.max_retries
        )
        if steady or force:
            self._accept(med, n, su, sv)
        else:
            self.retries += 1
        self._started, self._samples = None, []
