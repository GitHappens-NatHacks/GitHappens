"""Dwell selection: looking at the same target long enough selects it.

A target fires once per visit. Gaze must leave and come back (or reset() be called)
before the same target can fire again, so staring never double-books.
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
    def __init__(self, dwell_ms: int = 1000):
        self.dwell_ms = dwell_ms
        self.reset()

    def reset(self) -> None:
        self._target: Hashable | None = None
        self._since: int | None = None
        self._fired = False

    def consume(self) -> None:
        """Mark the current target as selected (e.g. by a blink) so dwell won't fire it again."""
        if self._target is not None:
            self._fired = True

    def update(self, target: Hashable | None, ts_ms: int) -> DwellState:
        if target is None:
            self.reset()
            return DwellState(None, 0.0, False)

        if target != self._target:
            self._target, self._since, self._fired = target, ts_ms, False

        if self._fired:
            return DwellState(target, 1.0, False)

        progress = min(1.0, (ts_ms - self._since) / self.dwell_ms) if self.dwell_ms > 0 else 1.0
        if progress >= 1.0:
            self._fired = True
            return DwellState(target, 1.0, True)
        return DwellState(target, progress, False)


def adaptive_dwell_ms(error_px: float) -> int:
    """Longer dwell when tracking is less accurate, within 600..2000 ms."""
    return max(600, min(2000, round(800 + 4 * error_px)))


def min_target_px(error_px: float) -> int:
    """Smallest button side that gaze can reliably hit at this accuracy."""
    return max(64, math.ceil(2 * error_px))
