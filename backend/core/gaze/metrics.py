"""Numbers for the pitch: how many gaze selections a task took, how long, how accurate."""

from __future__ import annotations


class GazeMetrics:
    def __init__(self) -> None:
        self._start: int | None = None
        self._end: int | None = None
        self._selections: list[tuple[int, str | None, str]] = []

    def start_task(self, ts_ms: int) -> None:
        self._start, self._end, self._selections = ts_ms, None, []

    def end_task(self, ts_ms: int) -> None:
        self._end = ts_ms

    def record_selection(self, ts_ms: int, intended: str | None, actual: str) -> None:
        """`intended` is what the user meant to pick when known (scripted test), else None."""
        self._selections.append((ts_ms, intended, actual))

    def summary(self) -> dict:
        judged = [(i, a) for _, i, a in self._selections if i is not None]
        accuracy = sum(i == a for i, a in judged) / len(judged) if judged else None
        task_ms = self._end - self._start if self._start is not None and self._end is not None else None
        return {"selections": len(self._selections), "accuracy": accuracy, "task_ms": task_ms}
