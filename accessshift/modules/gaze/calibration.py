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
