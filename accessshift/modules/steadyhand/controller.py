"""SteadyHand smoothing, optional simulated tremor, and metrics.

stabilize() processes coordinates; it does not capture mouse input.
Input and output must use the same coordinate system.
"""

from __future__ import annotations

import math
import os
import secrets
import time

from accessshift.modules.steadyhand.filter import OneEuroFilter


class SteadyHandController:
    def __init__(self, strength: float | None = None):
        self.fx = OneEuroFilter()
        self.fy = OneEuroFilter()

        self._enabled = os.getenv("STEADYHAND_ENABLED", "1") != "0"
        self._simulate_tremor = False
        self._strength = 0.0

        self._last_timestamp: float | None = None
        self._simulation_start: float | None = None

        self.reset_after_seconds = 0.5

        self.last_input = (0.0, 0.0)
        self.last_raw = (0.0, 0.0)
        self.last_stable = (0.0, 0.0)

        self._tremor_amplitude = 30.0
        self.pattern_seed = secrets.randbits(32)

        self.hits = 0
        self.misses = 0

        self._controller = None
        self.last_system_error: str | None = None

        initial_strength = (
            os.getenv("STEADYHAND_STRENGTH", "0.95")
            if strength is None
            else strength
        )
        self.strength = float(initial_strength)

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
        """0.0 = 0%, 1.0 = 100%, 2.0 = 200%."""
        value = float(value)

        if not math.isfinite(value):
            raise ValueError("Strength must be finite.")

        self._strength = max(0.0, min(2.0, value))

        # Above 100%, strengthen the filter.
        extra = max(0.0, self._strength - 1.0)

        cutoff = 0.65 * (0.15 / 0.65) ** extra
        beta = 0.004 * (0.001 / 0.004) ** extra

        self.fx.configure(cutoff, beta)
        self.fy.configure(cutoff, beta)

    @property
    def simulate_tremor(self) -> bool:
        return self._simulate_tremor

    @simulate_tremor.setter
    def simulate_tremor(self, value: bool) -> None:
        value = bool(value)

        if value != self._simulate_tremor:
            self._simulate_tremor = value
            self.restart_simulation()

    @property
    def tremor_amplitude(self) -> float:
        return self._tremor_amplitude

    @tremor_amplitude.setter
    def tremor_amplitude(self, value: float) -> None:
        value = float(value)

        if not math.isfinite(value) or value < 0:
            raise ValueError(
                "Amplitude must be finite and nonnegative."
            )

        self._tremor_amplitude = value

    def set_enabled(self, enabled: bool) -> None:
        self.enabled = enabled

    def set_strength(self, strength: float) -> None:
        self.strength = strength

    def set_simulate_tremor(self, enabled: bool) -> None:
        self.simulate_tremor = enabled

    def reset(self) -> None:
        """Clear smoothing history without clearing metrics."""
        self.fx.reset()
        self.fy.reset()
        self._last_timestamp = None

    def restart_simulation(self) -> None:
        """Replay the current pattern from its beginning."""
        self._simulation_start = None
        self.reset()

    def new_tremor_pattern(self, seed: int | None = None) -> int:
        """Generate a pattern or supply a seed for repeatable tests."""
        self.pattern_seed = (
            secrets.randbits(32)
            if seed is None
            else int(seed)
        ) & 0xFFFFFFFF

        self.restart_simulation()
        return self.pattern_seed

    def _noise_value(self, index: int, axis: int) -> float:
        """Deterministic pseudorandom value in [-1, 1)."""
        n = (
            ((index + 12345) * 374761393)
            ^ ((axis + 1) * 668265263)
            ^ self.pattern_seed
        ) & 0xFFFFFFFF

        n = ((n ^ (n >> 13)) * 1274126177) & 0xFFFFFFFF
        n = (n ^ (n >> 16)) & 0xFFFFFFFF

        return n / 4294967296.0 * 2.0 - 1.0

    def _noise_at(self, t: float, axis: int) -> float:
        index = math.floor(t)
        fraction = t - index

        fraction = fraction * fraction * (3.0 - 2.0 * fraction)

        first = self._noise_value(index, axis)
        second = self._noise_value(index + 1, axis)

        return first + fraction * (second - first)

    def tremor_offset(
        self,
        t: float | None = None,
    ) -> tuple[float, float]:
        """Generate synthetic jitter, not a clinical tremor model.

        Supply elapsed seconds to replay the same pattern.
        """
        t = (
            time.perf_counter()
            if t is None
            else float(t)
        )

        if not math.isfinite(t):
            raise ValueError("Simulation time must be finite.")

        block = math.floor(t / 0.45)
        local = t / 0.45 - block

        center = 0.25 + 0.5 * (
            self._noise_value(block, 7) + 1.0
        ) / 2.0

        width = 0.035 + 0.10 * (
            self._noise_value(block, 8) + 1.0
        ) / 2.0

        burst = 0.0

        if self._noise_value(block, 9) > 0.05:
            burst = math.exp(
                -((local - center) / width) ** 2
            )

        envelope = 0.15 + 1.3 * (
            (self._noise_at(t * 3.0, 2) + 1.0) / 2.0
        ) ** 2

        def offset(axis: int) -> float:
            fast_jitter = (
                0.85 * self._noise_at(t * 27.0, axis)
                + 0.4 * self._noise_at(t * 61.0, axis + 3)
            )

            slower_motion = (
                0.25 * self._noise_at(t * 5.0, axis + 12)
            )

            sudden_motion = (
                1.6 * burst
                * self._noise_value(block, axis + 20)
            )

            return self.tremor_amplitude * (
                envelope * fast_jitter
                + slower_motion
                + sudden_motion
            )

        return offset(0), offset(1)

    def stabilize(
        self,
        x: float,
        y: float,
        timestamp: float | None = None,
    ) -> tuple[float, float]:
        x = float(x)
        y = float(y)

        now = (
            time.perf_counter()
            if timestamp is None
            else float(timestamp)
        )

        if not all(math.isfinite(v) for v in (x, y, now)):
            raise ValueError(
                "Coordinates and timestamp must be finite."
            )

        if self._last_timestamp is not None:
            dt = now - self._last_timestamp

            if dt <= 0:
                return self.last_stable

            if dt > self.reset_after_seconds:
                self.reset()

        self.last_input = (x, y)

        # Simulation is OFF by default.
        if self.simulate_tremor:
            if self._simulation_start is None:
                self._simulation_start = now

            elapsed = now - self._simulation_start
            dx, dy = self.tremor_offset(elapsed)

            x += dx
            y += dy

        self.last_raw = (x, y)

        if self.enabled:
            filtered_x = self.fx.filter(x, now)
            filtered_y = self.fy.filter(y, now)

            # Never extrapolate beyond the filtered position.
            mix = min(1.0, self.strength)

            result = (
                x + mix * (filtered_x - x),
                y + mix * (filtered_y - y),
            )
        else:
            result = (x, y)

        self.last_stable = result
        self._last_timestamp = now

        return result

    def record_hit(self) -> None:
        self.hits += 1

    def record_miss(self) -> None:
        self.misses += 1

    def accuracy(self) -> float:
        total = self.hits + self.misses
        return self.hits / total if total else 0.0

    def reset_metrics(self) -> None:
        self.hits = 0
        self.misses = 0

    def try_enable_system_mouse(self) -> bool:
        """Initialize positioning, not system-wide stabilization."""
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
        """Move the OS pointer using screen coordinates.

        Do not feed generated movements back into an unguarded
        global mouse listener.
        """
        x = float(x)
        y = float(y)

        if not math.isfinite(x) or not math.isfinite(y):
            raise ValueError("Pointer coordinates must be finite.")

        if self._controller is None:
            return

        try:
            self._controller.position = (round(x), round(y))
            self.last_system_error = None

        except Exception as exc:
            self.last_system_error = str(exc)
            self._controller = None

    def disable_system_mouse(self) -> None:
        self._controller = None