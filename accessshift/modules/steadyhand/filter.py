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


class IntentionalHold:
    """Latch a drag only after sustained, coherent movement."""
    def __init__(self, metrics):
        self.metrics = metrics
        self.enabled = True
        self.anchor = None

    def press(self, stable, raw, now):
        self.anchor = stable
        self.origin = self.previous = raw
        self.press_timestamp = self.last_motion = now
        self.direction = None
        self.blocked = self.dragging = self.exceeded_drag_threshold = False

    def move(self, stable, raw, now):
        if self.anchor is None or not self.enabled or self.dragging:
            return stable
        dx, dy = (a - b for a, b in zip(raw, self.previous))
        length = math.hypot(dx, dy)
        changed_direction = False
        if length > 0.25:
            direction = (dx / length, dy / length)
            if (self.direction is None or now - self.last_motion > .08 or
                    sum(a*b for a, b in zip(direction, self.direction)) < .85):
                changed_direction = self.direction is not None
                self.direction = direction
                self.steady_since = now
            self.previous = raw
            self.last_motion = now
            if now - self.steady_since > .3 and math.dist(raw, self.origin) > 35:
                self.dragging = True
                return stable
        self.exceeded_drag_threshold |= math.dist(raw, self.origin) >= 8
        if not self.blocked and self.exceeded_drag_threshold and changed_direction:
            self.metrics.spastic_drags_prevented += 1
            self.blocked = True
        return self.anchor

    def release(self, stable, slipped):
        point = stable
        if self.enabled and self.anchor is not None and not self.dragging:
            if self.exceeded_drag_threshold and not self.blocked:
                self.metrics.spastic_drags_prevented += 1
            point = self.anchor
            if slipped:
                self.metrics.slip_clicks_rescued += 1
        self.anchor = None
        return point
