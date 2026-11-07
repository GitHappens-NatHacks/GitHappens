"""Task metrics, trial logging, and evaluation export for SteadyHand."""
from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable, Sequence


@dataclass(frozen=True)
class Click:
    seconds: float
    expected: str
    selected: str | None
    x: float
    y: float
    hit: bool


class Trial:
    """Tracks a sequence of target selection tasks within a designated mode."""

    def __init__(
        self,
        mode: str,
        sequence: Sequence[str],
        clock: Callable[[], float] = time.perf_counter,
    ):
        if not sequence:
            raise ValueError("A trial needs at least one target in its sequence")
        self.mode = str(mode)
        self.sequence = tuple(sequence)
        self.clock = clock
        self.started = clock()
        self.finished: float | None = None
        self.index = 0
        self.clicks: list[Click] = []

    @property
    def expected(self) -> str | None:
        return None if self.complete else self.sequence[self.index]

    @property
    def complete(self) -> bool:
        return self.index >= len(self.sequence)

    def record(self, selected: str | None, x: float, y: float) -> bool:
        if self.complete:
            return False
        now = self.clock()
        expected = self.expected
        hit = (selected is not None) and (selected == expected)
        self.clicks.append(Click(now - self.started, str(expected), selected, float(x), float(y), hit))
        if hit:
            self.index += 1
            if self.complete:
                self.finished = now
        return hit

    def summary(self) -> dict[str, Any]:
        hits = sum(1 for c in self.clicks if c.hit)
        count = len(self.clicks)
        elapsed = (self.finished if self.finished is not None else self.clock()) - self.started
        return {
            "mode": self.mode,
            "completed": self.complete,
            "hits": hits,
            "misses": count - hits,
            "interactions": count,
            "accuracy": (hits / count) if count > 0 else 0.0,
            "seconds": elapsed,
        }

    def export(self) -> dict[str, Any]:
        return {
            **self.summary(),
            "sequence": list(self.sequence),
            "clicks": [asdict(c) for c in self.clicks],
        }


def save_results(path: str | Path, trials: Sequence[Trial], extra: dict[str, Any] | None = None) -> None:
    """Save trial metrics to a JSON file, optionally attaching active application settings."""
    payload: dict[str, Any] | list[dict[str, Any]]
    if extra is not None:
        payload = {
            "timestamp": time.time(),
            "meta": extra,
            "trials": [t.export() for t in trials],
        }
    else:
        payload = [t.export() for t in trials]

    target_path = Path(path)
    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
