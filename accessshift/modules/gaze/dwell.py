"""Dwell selection: looking at the same target long enough selects it.

A target fires once per visit. Gaze must leave and come back (or reset() be called)
before the same target can fire again, so staring never double-books.
With grace_ms, a glance away shorter than that (webcam jitter) keeps the current
target and its progress instead of restarting the ring.
Pure logic: no Qt or camera imports.
"""

from __future__ import annotations

import math
from collections.abc import Hashable
from dataclasses import dataclass


@dataclass
class DwellState:
    target: Hashable | None
    progress: float  # 0..1
    fired: bool


class DwellSelector:
    def __init__(self, dwell_ms: int = 1000, grace_ms: int = 0):
        self.dwell_ms = dwell_ms
        self.grace_ms = grace_ms
        self.reset()

    def reset(self) -> None:
        self._target: Hashable | None = None
        self._since: int | None = None
        self._fired = False
        self._away_since: int | None = None

    def hold(self, ms: int) -> None:
        """Pause: don't count the last `ms` (e.g. eyes were closed) toward the dwell."""
        if self._since is not None:
            self._since += ms
        if self._away_since is not None:
            self._away_since += ms

    def consume(self) -> None:
        """Mark the current target as selected (e.g. by a blink) so dwell won't fire it again."""
        if self._target is not None:
            self._fired = True

    def update(self, target: Hashable | None, ts_ms: int) -> DwellState:
        if target != self._target and self._target is not None and self.grace_ms > 0:
            if self._away_since is None:
                self._away_since = ts_ms
            if ts_ms - self._away_since < self.grace_ms:
                return self._state(ts_ms, can_fire=False)  # brief glance away: keep counting
        if target == self._target:
            self._away_since = None

        if target is None:
            self.reset()
            return DwellState(None, 0.0, False)

        if target != self._target:
            self._target, self._since, self._fired, self._away_since = target, ts_ms, False, None
        return self._state(ts_ms, can_fire=True)

    def _state(self, ts_ms: int, can_fire: bool) -> DwellState:
        target = self._target

        if self._fired:
            return DwellState(target, 1.0, False)

        progress = min(1.0, (ts_ms - self._since) / self.dwell_ms) if self.dwell_ms > 0 else 1.0
        if progress >= 1.0 and can_fire:
            self._fired = True
            return DwellState(target, 1.0, True)
        return DwellState(target, progress, False)


# Same dwell for every button. Accuracy still drives snap radius, not click timing.
UNIFORM_DWELL_MS = 1100  # "Normal" selection speed; the control center passes the chosen speed


def adaptive_dwell_ms(error_px: float) -> int:
    """Return the uniform dwell. error_px kept for call-site compatibility."""
    del error_px
    return UNIFORM_DWELL_MS


def min_target_px(error_px: float) -> int:
    """Smallest button side that gaze can reliably hit at this accuracy."""
    return max(64, math.ceil(2 * error_px))
