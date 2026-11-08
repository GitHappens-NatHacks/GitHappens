"""One Euro filter for smoothing a single coordinate."""

from __future__ import annotations

import math
import time


class OneEuroFilter:
    def __init__(
        self,
        min_cutoff: float = 0.65,
        beta: float = 0.004,
        d_cutoff: float = 1.0,
    ):
        self.configure(min_cutoff, beta, d_cutoff)
        self.reset()

    def configure(
        self,
        min_cutoff: float,
        beta: float,
        d_cutoff: float = 1.0,
    ) -> None:
        values = tuple(map(float, (min_cutoff, beta, d_cutoff)))

        if not all(math.isfinite(v) for v in values):
            raise ValueError("Filter parameters must be finite.")

        if values[0] <= 0 or values[2] <= 0 or values[1] < 0:
            raise ValueError(
                "Cutoffs must be positive and beta cannot be negative."
            )

        self.min_cutoff, self.beta, self.d_cutoff = values

    def reset(self) -> None:
        self.last_time: float | None = None
        self.last_raw: float | None = None
        self.filtered: float | None = None
        self.filtered_velocity = 0.0

    @staticmethod
    def _alpha(cutoff: float, dt: float) -> float:
        return dt / (dt + 1.0 / (2.0 * math.pi * cutoff))

    def filter(
        self,
        x: float,
        timestamp: float | None = None,
    ) -> float:
        x = float(x)
        now = (
            time.perf_counter()
            if timestamp is None
            else float(timestamp)
        )

        if not math.isfinite(x) or not math.isfinite(now):
            raise ValueError("Sample and timestamp must be finite.")

        # Start directly at the first position.
        if self.last_time is None:
            self.last_time = now
            self.last_raw = x
            self.filtered = x
            return x

        dt = now - self.last_time

        # Ignore duplicate or backward timestamps.
        if dt <= 0:
            return self.filtered

        velocity = (x - self.last_raw) / dt

        derivative_alpha = self._alpha(self.d_cutoff, dt)
        self.filtered_velocity += derivative_alpha * (
            velocity - self.filtered_velocity
        )

        cutoff = (
            self.min_cutoff
            + self.beta * abs(self.filtered_velocity)
        )

        position_alpha = self._alpha(cutoff, dt)
        self.filtered += position_alpha * (x - self.filtered)

        self.last_time = now
        self.last_raw = x

        return self.filtered