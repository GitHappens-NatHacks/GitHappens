from __future__ import annotations
"""Task metrics independent of Qt and the smoothing controller."""
import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class Click:
    seconds: float
    expected: str
    selected: str | None
    x: float
    y: float
    hit: bool


class Trial:
    def __init__(self, mode, sequence, clock=time.perf_counter):
        if not sequence:
            raise ValueError('A trial needs at least one target')
        self.mode = mode
        self.sequence = tuple(sequence)
        self.clock = clock
        self.started = clock()
        self.finished = None
        self.index = 0
        self.clicks = []

    @property
    def expected(self):
        return None if self.complete else self.sequence[self.index]

    @property
    def complete(self):
        return self.index == len(self.sequence)

    def record(self, selected, x, y):
        if self.complete:
            return False
        now = self.clock()
        hit = selected == self.expected
        self.clicks.append(Click(now-self.started, self.expected, selected, x, y, hit))
        if hit:
            self.index += 1
            if self.complete:
                self.finished = now
        return hit

    def summary(self):
        hits = sum(c.hit for c in self.clicks)
        count = len(self.clicks)
        return dict(mode=self.mode, completed=self.complete, hits=hits,
                    misses=count-hits, interactions=count,
                    accuracy=hits/count if count else None,
                    seconds=(self.finished if self.finished is not None else self.clock())-self.started)

    def export(self):
        return {**self.summary(), 'sequence': self.sequence,
                'clicks': [asdict(c) for c in self.clicks]}


def save_results(path, trials):
    Path(path).write_text(json.dumps([t.export() for t in trials], indent=2), encoding='utf-8')
