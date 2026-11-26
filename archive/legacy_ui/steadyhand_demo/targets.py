"""Framework-independent target selection. Coordinates share one local space."""
from dataclasses import dataclass
from math import hypot, isfinite


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
            raise ValueError('Targets need an ID and finite geometry')
        if self.width <= 0 or self.height <= 0:
            raise ValueError('Target dimensions must be positive')

    def contains(self, x, y, padding=0):
        return (self.x-padding <= x <= self.x+self.width+padding
                and self.y-padding <= y <= self.y+self.height+padding)

    def distance(self, x, y):
        return hypot(max(self.x-x, 0, x-self.x-self.width),
                     max(self.y-y, 0, y-self.y-self.height))


class TargetManager:
    def __init__(self, targets=(), padding=16):
        if not isfinite(padding) or padding < 0:
            raise ValueError('Padding must be finite and nonnegative')
        self.padding = padding
        self.set_targets(targets)

    def set_targets(self, targets):
        targets = tuple(targets)
        if len({t.id for t in targets}) != len(targets):
            raise ValueError('Target IDs must be unique')
        self.targets = targets

    def select(self, x, y, assisted=False):
        """Direct hits win. Expanded overlaps use distance then stable ID.

        Disabled controls are never candidates. The expected task target is
        deliberately not an argument: selection must not know the answer.
        """
        if not all(isfinite(v) for v in (x, y)):
            raise ValueError('Coordinates must be finite')
        active = [t for t in self.targets if t.enabled]
        direct = [t for t in active if t.contains(x, y)]
        if direct:
            return min(direct, key=lambda t: (t.width*t.height, t.id))
        if not assisted:
            return None
        candidates = [t for t in active if t.contains(x, y, self.padding)]
        return min(candidates, key=lambda t: (t.distance(x, y), t.id), default=None)
