"""1-Euro filter for pointer smoothing (Casiez et al.)."""

from __future__ import annotations

import math
import time


class _LowPass:
    def __init__(self):
        self.hat_x = 0.0
        self.initialized = False

    def filter(self, x: float, alpha: float) -> float:
        if not self.initialized:
            self.initialized = True
            self.hat_x = x
            return x
        self.hat_x = alpha * x + (1.0 - alpha) * self.hat_x
        return self.hat_x


def _alpha(cutoff: float, dt: float) -> float:
    tau = 1.0 / (2.0 * math.pi * cutoff)
    return 1.0 / (1.0 + tau / dt)


class OneEuroFilter:
    def __init__(self, min_cutoff: float = 1.0, beta: float = 0.007, d_cutoff: float = 1.0):
        self.min_cutoff = min_cutoff
        self.beta = beta
        self.d_cutoff = d_cutoff
        self.x_filter = _LowPass()
        self.dx_filter = _LowPass()
        self.last_time: float | None = None

    def filter(self, x: float, timestamp: float | None = None) -> float:
        now = timestamp if timestamp is not None else time.perf_counter()
        dt = 1 / 60 if self.last_time is None else max(1e-3, now - self.last_time)
        self.last_time = now

        prev = self.x_filter.hat_x
        dx = 0.0 if not self.x_filter.initialized else (x - prev) / dt
        edx = self.dx_filter.filter(dx, _alpha(self.d_cutoff, dt))
        cutoff = self.min_cutoff + self.beta * abs(edx)
        return self.x_filter.filter(x, _alpha(cutoff, dt))
