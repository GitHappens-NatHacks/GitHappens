"""Deliberate blink detection from eye aspect ratio (EAR).

A selection blink is a closure lasting min_ms..max_ms. Natural blinks (~100-150 ms)
are too short, and resting the eyes is too long. Time-based, so it works at any frame rate.
"""

from __future__ import annotations

from statistics import median


def eye_aspect_ratio(eye):
    vertical_1 = ((eye[1][0] - eye[5][0]) ** 2 + (eye[1][1] - eye[5][1]) ** 2) ** 0.5
    vertical_2 = ((eye[2][0] - eye[4][0]) ** 2 + (eye[2][1] - eye[4][1]) ** 2) ** 0.5
    horizontal = ((eye[0][0] - eye[3][0]) ** 2 + (eye[0][1] - eye[3][1]) ** 2) ** 0.5
    if horizontal < 1e-6:
        return 0.0
    return (vertical_1 + vertical_2) / (2.0 * horizontal)


class BlinkDetector:
    def __init__(
        self,
        ear_threshold: float = 0.21,
        min_ms: int = 400,
        max_ms: int = 1500,
        cooldown_ms: int = 700,
    ):
        self.ear_threshold = ear_threshold
        self.min_ms = min_ms
        self.max_ms = max_ms
        self.cooldown_ms = cooldown_ms
        self._closed_since: int | None = None
        self._last_fired: int | None = None

    def calibrate_open(self, ears: list[float]) -> None:
        """Set the closed threshold from EAR samples taken with eyes open."""
        if ears:
            self.ear_threshold = 0.75 * median(ears)

    def closed_ms(self, ts_ms: int) -> int:
        """How long the eyes have been closed right now (0 if open)."""
        return 0 if self._closed_since is None else max(0, ts_ms - self._closed_since)

    def update(self, ear: float, ts_ms: int) -> bool:
        """Return True on the frame the eyes reopen after a deliberate blink."""
        if ear < self.ear_threshold:
            if self._closed_since is None:
                self._closed_since = ts_ms
            return False

        if self._closed_since is None:
            return False

        duration = ts_ms - self._closed_since
        self._closed_since = None
        if not (self.min_ms <= duration <= self.max_ms):
            return False
        if self._last_fired is not None and ts_ms - self._last_fired < self.cooldown_ms:
            return False
        self._last_fired = ts_ms
        return True
