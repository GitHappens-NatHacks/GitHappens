"""Task metrics, trial logging, and evaluation export for SteadyHand."""
from __future__ import annotations

import numpy as np

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

class MotorTelemetry:
    """Four-second raw displacement spectrum, updated twice per second."""

    def __init__(self):
        from collections import deque
        self.samples = deque(maxlen=512)
        self.history = []
        self.latest = None
        self.spastic_drags_prevented = 0
        self.slip_clicks_rescued = 0

    def reset_window(self):
        self.samples.clear()
        self.latest = None

    def sample(self, x, y, now, simulated=False):
        if self.samples and now <= self.samples[-1][0]:
            return
        if self.samples and now - self.samples[-1][0] > 0.08:
            self.reset_window()
        self.samples.append((now, x, y))
        while now - self.samples[0][0] > 4.0:
            self.samples.popleft()
        if len(self.samples) < 100 or now - self.samples[0][0] < 3:
            return
        if self.latest and now - self.latest["sample_time"] < 0.5:
            return
        times, xs, ys = np.asarray(self.samples).T
        grid = np.arange(times[0], times[-1], 1 / 60)
        # Separate signed axes preserve the fundamental of a back-and-forth motion.
        taper = np.hanning(len(grid))
        power = np.zeros(len(grid) // 2 + 1)
        for axis in (xs, ys):
            values = np.interp(grid, times, axis)
            values -= np.linspace(values[0], values[-1], len(grid))
            power += abs(np.fft.rfft((values - values.mean()) * taper)) ** 2
        hz = np.fft.rfftfreq(len(grid), 1 / 60)
        band = (hz >= 4) & (hz <= 7)
        total = power[(hz >= .5) & (hz <= 12)].sum()
        index = float(100 * power[band].sum() / total) if total > 1e-6 else 0.
        dominant = float(hz[band][power[band].argmax()]) if index >= 10 else None
        self.latest = dict(timestamp=time.time(), sample_time=now, tremor_index=round(index, 2),
                           dominant_hz=dominant, medication_state_estimate="OFF" if index >= 50 else "ON",
                           simulated=simulated)
        self.history.append(self.latest)

    def export(self, path):
        import csv
        with Path(path).open("w", newline="", encoding="utf-8") as stream:
            if str(path).lower().endswith(".csv"):
                fields = ("timestamp", "sample_time", "tremor_index", "dominant_hz",
                          "medication_state_estimate", "simulated")
                writer = csv.DictWriter(stream, fieldnames=fields)
                writer.writeheader()
                writer.writerows(self.history)
            else:
                json.dump(self.history, stream, indent=2)
