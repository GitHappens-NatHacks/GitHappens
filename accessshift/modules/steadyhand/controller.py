"""Coordinate processing and settings for SteadyHand.

Provides in-app smoothing and optional simulated tremor.

The optional pynput methods only provide cursor positioning.
They do not implement system-wide input interception or stabilization.
"""

from __future__ import annotations

import math
import os
import time

from accessshift.modules.steadyhand.filter import OneEuroFilter


class SteadyHandController:
    def __init__(self, strength: float | None = None):
        self.fx = OneEuroFilter(min_cutoff=1.2, beta=0.02)
        self.fy = OneEuroFilter(min_cutoff=1.2, beta=0.02)

        self._enabled = os.getenv("STEADYHAND_ENABLED", "1") != "0"
        self._simulate_tremor = False
        self._strength = 0.0

        initial_strength = (
            os.getenv("STEADYHAND_STRENGTH", "0.7")
            if strength is None
            else strength
        )
        self.strength = float(initial_strength)

        # All coordinates must use the same coordinate system.
        self.last_input = (0.0, 0.0)
        self.last_raw = (0.0, 0.0)
        self.last_stable = (0.0, 0.0)

        self._last_timestamp: float | None = None

        # Reset after an input gap to avoid resuming with stale history.
        self.reset_after_seconds = 0.5

        # Demo parameters: amplitude in pixels.
        self.tremor_amplitude = 10.0
        self._simulation_start: float | None = None

        self.hits = 0
        self.misses = 0

        self._controller = None
        self.last_system_error: str | None = None

    @property
    def enabled(self) -> bool:
        return self._enabled

    @enabled.setter
    def enabled(self, value: bool) -> None:
        value = bool(value)

        if value != self._enabled:
            self._enabled = value
            self.reset()

    @property
    def strength(self) -> float:
        return self._strength

    @strength.setter
    def strength(self, value: float) -> None:
        value = float(value)

        if not math.isfinite(value):
            raise ValueError("Strength must be finite.")

        self._strength = max(0.0, min(1.0, value))

    @property
    def simulate_tremor(self) -> bool:
        return self._simulate_tremor

    @simulate_tremor.setter
    def simulate_tremor(self, value: bool) -> None:
        value = bool(value)

        if value != self._simulate_tremor:
            self._simulate_tremor = value
            self._simulation_start = None
            self.reset()

    # Methods are available for explicit UI connections.
    # Properties above also support your existing direct assignments.

    def set_enabled(self, enabled: bool) -> None:
        self.enabled = enabled

    def set_strength(self, strength: float) -> None:
        self.strength = strength

    def set_simulate_tremor(self, enabled: bool) -> None:
        self.simulate_tremor = enabled

    def reset(self) -> None:
        """Clear motion history without clearing benchmark results."""
        self.fx.reset()
        self.fy.reset()
        self._last_timestamp = None

    def tremor_offset(
        self,
        t: float | None = None,
    ) -> tuple[float, float]:
        """Return synthetic jitter for demonstrations.

        Frequencies below are in Hz. This is not a clinical tremor model.
        Supply elapsed seconds for reproducible playback.
        """
        t = time.perf_counter() if t is None else float(t)
        amplitude = float(self.tremor_amplitude)

        if not math.isfinite(t):
            raise ValueError("Time must be finite.")

        if not math.isfinite(amplitude) or amplitude < 0:
            raise ValueError("Tremor amplitude must be finite and nonnegative.")

        phase = 2.0 * math.pi * t

        dx = amplitude * (
            math.sin(4.5 * phase)
            + 0.35 * math.sin(7.5 * phase)
        )

        dy = amplitude * (
            math.sin(5.0 * phase)
            + 0.35 * math.sin(8.5 * phase)
        )

        return dx, dy

    def stabilize(
        self,
        x: float,
        y: float,
        timestamp: float | None = None,
    ) -> tuple[float, float]:
        """Process a position and return assisted coordinates.

        Input and output use the same coordinate system.
        This method does not move the operating-system cursor.
        """
        x = float(x)
        y = float(y)
        now = (
            time.perf_counter()
            if timestamp is None
            else float(timestamp)
        )

        if not all(math.isfinite(v) for v in (x, y, now)):
            raise ValueError("Coordinates and timestamp must be finite.")

        if self._last_timestamp is not None:
            dt = now - self._last_timestamp

            # Ignore samples that do not advance time.
            if dt <= 0:
                return self.last_stable

            if dt > self.reset_after_seconds:
                self.reset()

        self.last_input = (x, y)

        if self.simulate_tremor:
            if self._simulation_start is None:
                self._simulation_start = now

            elapsed = now - self._simulation_start
            dx, dy = self.tremor_offset(elapsed)

            x += dx
            y += dy

        # "raw" includes synthetic jitter when simulation is enabled.
        self.last_raw = (x, y)

        if self.enabled:
            filtered_x = self.fx.filter(x, now)
            filtered_y = self.fy.filter(y, now)

            mix = self.strength

            output = (
                x + mix * (filtered_x - x),
                y + mix * (filtered_y - y),
            )
        else:
            output = (x, y)

        self.last_stable = output
        self._last_timestamp = now

        return output

    def record_hit(self) -> None:
        self.hits += 1

    def record_miss(self) -> None:
        self.misses += 1

    def accuracy(self) -> float:
        """Return accuracy as a fraction between 0 and 1."""
        total = self.hits + self.misses

        if total == 0:
            return 0.0

        return self.hits / total

    def reset_metrics(self) -> None:
        self.hits = 0
        self.misses = 0

    def try_enable_system_mouse(self) -> bool:
        """Create an optional cursor-positioning backend.

        Success means initialization succeeded, not that system-wide
        stabilization or all required permissions are available.
        """
        try:
            from pynput.mouse import Controller

            self._controller = Controller()
            self.last_system_error = None
            return True

        except Exception as exc:
            self._controller = None
            self.last_system_error = str(exc)
            return False

    def move_system_pointer(self, x: float, y: float) -> None:
        """Move the OS cursor using SCREEN coordinates.

        Do not call this from an unguarded global mouse listener:
        generated movement can feed back into that listener.
        """
        if self._controller is None:
            return

        x = float(x)
        y = float(y)

        if not math.isfinite(x) or not math.isfinite(y):
            raise ValueError("Pointer coordinates must be finite.")

        try:
            self._controller.position = (round(x), round(y))
            self.last_system_error = None

        except Exception as exc:
            self.last_system_error = str(exc)
            self._controller = None

    def disable_system_mouse(self) -> None:
        self._controller = None