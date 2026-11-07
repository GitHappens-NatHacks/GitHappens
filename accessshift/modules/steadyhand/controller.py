"""Pointer stabilization controller.

Starts with in-app coordinate smoothing. System-wide mouse injection via pynput
is opt-in once Accessibility permission is granted on macOS.
"""

from __future__ import annotations

import math
import os
import time

from accessshift.modules.steadyhand.filter import OneEuroFilter


class SteadyHandController:
    def __init__(self, strength: float | None = None):
        self.strength = float(os.getenv("STEADYHAND_STRENGTH", "0.7") if strength is None else strength)
        self.enabled = os.getenv("STEADYHAND_ENABLED", "1") != "0"
        self.simulate_tremor = False
        self.fx = OneEuroFilter(min_cutoff=1.2, beta=0.02)
        self.fy = OneEuroFilter(min_cutoff=1.2, beta=0.02)
        self._listener = None
        self._controller = None
        self.last_raw = (0.0, 0.0)
        self.last_stable = (0.0, 0.0)
        self.hits = 0
        self.misses = 0

    def tremor_offset(self, t: float | None = None) -> tuple[float, float]:
        t = time.perf_counter() if t is None else t
        amp = 10.0
        return (
            amp * math.sin(t * 28) + amp * 0.35 * math.sin(t * 47),
            amp * math.cos(t * 31) + amp * 0.35 * math.cos(t * 53),
        )

    def stabilize(self, x: float, y: float, timestamp: float | None = None) -> tuple[float, float]:
        if self.simulate_tremor:
            dx, dy = self.tremor_offset(timestamp)
            x, y = x + dx, y + dy
        self.last_raw = (x, y)
        if not self.enabled:
            self.last_stable = (x, y)
            return x, y
        sx = self.fx.filter(x, timestamp)
        sy = self.fy.filter(y, timestamp)
        mix = min(1.0, max(0.0, self.strength))
        out = (x * (1 - mix) + sx * mix, y * (1 - mix) + sy * mix)
        self.last_stable = out
        return out

    def record_hit(self) -> None:
        self.hits += 1

    def record_miss(self) -> None:
        self.misses += 1

    def accuracy(self) -> float:
        total = self.hits + self.misses
        return 0.0 if total == 0 else self.hits / total

    def try_enable_system_mouse(self) -> bool:
        """Attempt pynput Controller; returns False if OS blocks it."""
        try:
            from pynput.mouse import Controller

            self._controller = Controller()
            return True
        except Exception:
            self._controller = None
            return False

    def move_system_pointer(self, x: float, y: float) -> None:
        if self._controller is None:
            return
        self._controller.position = (int(x), int(y))
