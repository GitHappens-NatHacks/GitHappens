"""One Euro filtering for a single coordinate.

This module contains only smoothing math.
It does not capture mouse input or move the system cursor.
"""

from __future__ import annotations

import math
import time


class _LowPass:
    def __init__(self):
        self.value: float | None = None

    def reset(self) -> None:
        self.value = None

    def filter(self, value: float, alpha: float) -> float:
        if self.value is None:
            self.value = value
        else:
            self.value += alpha * (value - self.value)

        return self.value


def _alpha(cutoff: float, dt: float) -> float:
    """Calculate smoothing weight from cutoff in Hz and time in seconds."""
    tau = 1.0 / (2.0 * math.pi * cutoff)
    return dt / (dt + tau)


class OneEuroFilter:
    def __init__(
        self,
        min_cutoff: float = 1.0,
        beta: float = 0.007,
        d_cutoff: float = 1.0,
    ):
        self.min_cutoff = float(min_cutoff)
        self.beta = float(beta)
        self.d_cutoff = float(d_cutoff)

        self._validate_parameters()

        self.x_filter = _LowPass()
        self.dx_filter = _LowPass()

        self.last_time: float | None = None
        self.last_raw: float | None = None

    def _validate_parameters(self) -> None:
        parameters = (
            self.min_cutoff,
            self.beta,
            self.d_cutoff,
        )

        if not all(math.isfinite(value) for value in parameters):
            raise ValueError("Filter parameters must be finite.")

        if self.min_cutoff <= 0:
            raise ValueError("min_cutoff must be greater than zero.")

        if self.d_cutoff <= 0:
            raise ValueError("d_cutoff must be greater than zero.")

        if self.beta < 0:
            raise ValueError("beta cannot be negative.")

    def reset(self) -> None:
        """Discard history. The next sample passes through unchanged."""
        self.x_filter.reset()
        self.dx_filter.reset()

        self.last_time = None
        self.last_raw = None

    def filter(
        self,
        x: float,
        timestamp: float | None = None,
    ) -> float:
        """Filter one sample.

        timestamp must use a monotonic clock and be measured in seconds.
        Duplicate or backward timestamps leave the filter unchanged.
        """
        x = float(x)
        now = (
            time.perf_counter()
            if timestamp is None
            else float(timestamp)
        )

        if not math.isfinite(x) or not math.isfinite(now):
            raise ValueError("Sample and timestamp must be finite.")

        self._validate_parameters()

        # Initialize directly at the first position.
        if self.last_time is None:
            self.last_time = now
            self.last_raw = x
            self.dx_filter.filter(0.0, 1.0)
            return self.x_filter.filter(x, 1.0)

        dt = now - self.last_time

        if dt <= 0:
            return self.x_filter.value

        # Estimate velocity from successive raw samples.
        velocity = (x - self.last_raw) / dt

        filtered_velocity = self.dx_filter.filter(
            velocity,
            _alpha(self.d_cutoff, dt),
        )

        # Faster motion raises the cutoff, reducing smoothing and lag.
        cutoff = self.min_cutoff + self.beta * abs(filtered_velocity)

        result = self.x_filter.filter(
            x,
            _alpha(cutoff, dt),
        )

        self.last_time = now
        self.last_raw = x

        return result