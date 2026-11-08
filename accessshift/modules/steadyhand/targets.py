"""Framework-independent target selection and bounding box expansion.

Coordinates share one local space. Used by SteadyHand to assist users
with motor tremors to click smaller or closely-spaced UI targets.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import hypot, isfinite
from typing import Sequence


@dataclass(frozen=True)
class Target:
    id: str
    label: str
    x: float
    y: float
    width: float
    height: float
    enabled: bool = True

    def __post_init__(self):
        if not self.id or not all(isfinite(v) for v in (self.x, self.y, self.width, self.height)):
            raise ValueError("Targets need an ID and finite geometry")
        if self.width <= 0 or self.height <= 0:
            raise ValueError("Target dimensions must be positive")

    def contains(self, x: float, y: float, padding: float = 0.0) -> bool:
        return (
            self.x - padding <= x <= self.x + self.width + padding
            and self.y - padding <= y <= self.y + self.height + padding
        )

    def distance(self, x: float, y: float) -> float:
        return hypot(
            max(self.x - x, 0.0, x - self.x - self.width),
            max(self.y - y, 0.0, y - self.y - self.height),
        )


class TargetManager:
    """Manages spatial candidate targets and assisted selection logic."""

    def __init__(self, targets: Sequence[Target] = (), padding: float = 16.0):
        if not isfinite(padding) or padding < 0:
            raise ValueError("Padding must be finite and nonnegative")
        self.padding = float(padding)
        self.set_targets(targets)

    def set_targets(self, targets: Sequence[Target]) -> None:
        targets_tuple = tuple(targets)
        if len({t.id for t in targets_tuple}) != len(targets_tuple):
            raise ValueError("Target IDs must be unique")
        self.targets = targets_tuple

    def select(self, x: float, y: float, assisted: bool = False) -> Target | None:
        """Select a target given coordinates.

        Direct hits always take precedence. If assisted is True and no direct hit
        occurred, nearby active targets within padding range are scored by distance.
        The expected task target is deliberately not considered here to keep selection unbiased.
        """
        if not all(isfinite(v) for v in (x, y)):
            raise ValueError("Coordinates must be finite")
        active = [t for t in self.targets if t.enabled]
        direct = [t for t in active if t.contains(x, y)]
        if direct:
            return min(direct, key=lambda t: (t.width * t.height, t.id))
        if not assisted:
            return None
        candidates = [t for t in active if t.contains(x, y, self.padding)]
        return min(candidates, key=lambda t: (t.distance(x, y), t.id), default=None)
