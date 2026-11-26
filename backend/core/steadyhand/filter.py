"""One Euro filter adapter, Click-Freeze hold guard, double-click bounce guard, and scroll jitter filter."""

from __future__ import annotations

import math
import time

from OneEuroFilter import OneEuroFilter as _PyPIOneEuroFilter


class OneEuroFilter:
    """Thread-safe scalar One Euro filter wrapping the official PyPI package."""

    def __init__(
        self,
        min_cutoff: float = 0.65,
        beta: float = 0.004,
        d_cutoff: float = 1.0,
    ):
        self.min_cutoff = float(min_cutoff)
        self.beta = float(beta)
        self.d_cutoff = float(d_cutoff)
        self._impl: _PyPIOneEuroFilter | None = None
        self.last_time: float | None = None
        self.filtered: float | None = None
        self.configure(min_cutoff, beta, d_cutoff)
        self.reset()

    def configure(
        self,
        min_cutoff: float,
        beta: float,
        d_cutoff: float = 1.0,
    ) -> None:
        values = tuple(map(float, (min_cutoff, beta, d_cutoff)))
        if not all(math.isfinite(v) for v in values):
            raise ValueError("Filter parameters must be finite.")
        if values[0] <= 0 or values[2] <= 0 or values[1] < 0:
            raise ValueError("Cutoffs must be positive and beta cannot be negative.")

        self.min_cutoff, self.beta, self.d_cutoff = values
        if self._impl is not None:
            self._impl.setMinCutoff(self.min_cutoff)
            self._impl.setBeta(self.beta)
            self._impl.setDerivateCutoff(self.d_cutoff)

    def reset(self) -> None:
        self._impl = _PyPIOneEuroFilter(
            freq=60.0,
            mincutoff=self.min_cutoff,
            beta=self.beta,
            dcutoff=self.d_cutoff,
        )
        self.last_time = None
        self.filtered = None

    def filter(
        self,
        x: float,
        timestamp: float | None = None,
    ) -> float:
        x = float(x)
        now = time.perf_counter() if timestamp is None else float(timestamp)
        if not math.isfinite(x) or not math.isfinite(now):
            raise ValueError("Sample and timestamp must be finite.")

        if self.last_time is not None and now <= self.last_time:
            return float(self.filtered if self.filtered is not None else x)

        assert self._impl is not None
        out = float(self._impl(x, now))
        self.last_time = now
        self.filtered = out
        return out


class IntentionalHold:
    """Click-Freeze and ballistic anti-drag guard.

    Freezes pointer coordinates from MouseDown until MouseUp or until intentional
    coherent displacement exceeds drag_release_px past hold_seconds / click_freeze_ms.
    """

    def __init__(self, metrics):
        self.metrics = metrics
        self.enabled = True
        self.anchor = None
        self.drag_threshold_px = 8.0
        self.hold_seconds = 0.3
        self.latch_distance_px = 35.0
        self.click_freeze_ms = 180
        self.drag_release_px = 25.0
        self.origin = (0.0, 0.0)
        self.previous = (0.0, 0.0)
        self.press_timestamp = 0.0
        self.last_motion = 0.0
        self.steady_since = 0.0
        self.direction = None
        self.blocked = False
        self.dragging = False
        self.exceeded_drag_threshold = False

    @property
    def click_freeze_active(self) -> bool:
        return bool(self.enabled and self.anchor is not None and not self.dragging)

    def configure(
        self,
        *,
        drag_threshold_px: float | None = None,
        hold_seconds: float | None = None,
        latch_distance_px: float | None = None,
        click_freeze_ms: int | None = None,
        drag_release_px: float | None = None,
    ) -> None:
        if drag_threshold_px is not None:
            self.drag_threshold_px = max(2.0, min(40.0, float(drag_threshold_px)))
        if hold_seconds is not None:
            self.hold_seconds = max(0.08, min(1.5, float(hold_seconds)))
        if latch_distance_px is not None:
            self.latch_distance_px = max(10.0, min(120.0, float(latch_distance_px)))
        if click_freeze_ms is not None:
            self.click_freeze_ms = max(0, min(500, int(click_freeze_ms)))
        if drag_release_px is not None:
            self.drag_release_px = max(8.0, min(80.0, float(drag_release_px)))

    def press(self, stable, raw, now):
        self.anchor = stable
        self.origin = self.previous = raw
        self.press_timestamp = self.last_motion = self.steady_since = now
        self.direction = None
        self.blocked = self.dragging = self.exceeded_drag_threshold = False

    def move(self, stable, raw, now):
        if self.anchor is None or not self.enabled or self.dragging:
            return stable

        freeze_elapsed_ms = (now - self.press_timestamp) * 1000.0
        origin_dist = math.dist(raw, self.origin)
        in_click_freeze = freeze_elapsed_ms < self.click_freeze_ms and origin_dist < self.drag_release_px

        dx, dy = (a - b for a, b in zip(raw, self.previous))
        length = math.hypot(dx, dy)
        changed_direction = False
        if length > 0.25:
            direction = (dx / length, dy / length)
            if (
                self.direction is None
                or now - self.last_motion > 0.1
                or sum(a * b for a, b in zip(direction, self.direction)) < 0.72
            ):
                changed_direction = self.direction is not None
                self.direction = direction
                self.steady_since = now
            self.previous = raw
            self.last_motion = now
            if (
                not in_click_freeze
                and now - self.steady_since > self.hold_seconds
                and origin_dist > max(self.latch_distance_px, self.drag_release_px)
            ):
                self.dragging = True
                return stable

        self.exceeded_drag_threshold |= origin_dist >= self.drag_threshold_px
        if not self.blocked and self.exceeded_drag_threshold and changed_direction:
            self.metrics.spastic_drags_prevented += 1
            self.blocked = True
        return self.anchor

    def release(self, stable, slipped):
        point = stable
        if self.enabled and self.anchor is not None and not self.dragging:
            if self.exceeded_drag_threshold and not self.blocked:
                self.metrics.spastic_drags_prevented += 1
            point = self.anchor
            if slipped:
                self.metrics.slip_clicks_rescued += 1
        self.anchor = None
        return point


class ClickBounceGuard:
    """Blocks involuntary tremor double-click bounce and accidental adjacent right-clicks."""

    def __init__(self, metrics, *, click_debounce_ms: int = 70, right_click_guard: bool = True):
        self.metrics = metrics
        self.click_debounce_ms = max(0, min(250, int(click_debounce_ms)))
        self.right_click_guard = bool(right_click_guard)
        self._last_release_ts: dict[str, float] = {}
        self._suppressed_down: set[str] = set()

    def configure(
        self,
        *,
        click_debounce_ms: int | None = None,
        right_click_guard: bool | None = None,
    ) -> None:
        if click_debounce_ms is not None:
            self.click_debounce_ms = max(0, min(250, int(click_debounce_ms)))
        if right_click_guard is not None:
            self.right_click_guard = bool(right_click_guard)

    def reset(self) -> None:
        self._last_release_ts.clear()
        self._suppressed_down.clear()

    def allow_down(self, button: str, now: float) -> bool:
        """Return True if button-down is intentional, False if blocked as tremor bounce."""
        btn = (button or "left").lower()
        if hasattr(self.metrics, "total_clicks"):
            self.metrics.total_clicks += 1

        last_up = self._last_release_ts.get(btn)
        if self.click_debounce_ms > 0 and last_up is not None:
            elapsed_ms = (now - last_up) * 1000.0
            if 0.0 <= elapsed_ms < self.click_debounce_ms:
                self._suppressed_down.add(btn)
                if hasattr(self.metrics, "double_clicks_blocked"):
                    self.metrics.double_clicks_blocked += 1
                return False

        # Guard accidental right-button finger twitch immediately after a left click
        if self.right_click_guard and btn == "right":
            last_left = self._last_release_ts.get("left")
            if last_left is not None and 0.0 <= (now - last_left) * 1000.0 < 90.0:
                self._suppressed_down.add(btn)
                if hasattr(self.metrics, "double_clicks_blocked"):
                    self.metrics.double_clicks_blocked += 1
                return False

        self._suppressed_down.discard(btn)
        return True

    def allow_up(self, button: str, now: float) -> bool:
        """Return True if button-up should pass through, False if paired with a blocked bounce."""
        btn = (button or "left").lower()
        if btn in self._suppressed_down:
            self._suppressed_down.discard(btn)
            return False
        self._last_release_ts[btn] = float(now)
        return True


class ScrollJitterFilter:
    """Suppresses rapid opposite-direction micro-scroll reversals caused by finger tremor."""

    def __init__(self, metrics, *, enabled: bool = True, reversal_window_ms: int = 120):
        self.metrics = metrics
        self.enabled = bool(enabled)
        self.reversal_window_ms = max(40, min(400, int(reversal_window_ms)))
        self._last_sign = 0
        self._last_ts: float | None = None

    def configure(self, *, enabled: bool | None = None) -> None:
        if enabled is not None:
            self.enabled = bool(enabled)
            if not self.enabled:
                self._last_sign = 0
                self._last_ts = None

    def reset(self) -> None:
        self._last_sign = 0
        self._last_ts = None

    def should_suppress(self, delta: float, now: float) -> bool:
        """Return True if scroll step is a small tremor reversal within reversal_window_ms."""
        if not self.enabled or delta == 0:
            return False
        sign = 1 if delta > 0 else -1
        if self._last_ts is not None and self._last_sign != 0:
            elapsed_ms = (now - self._last_ts) * 1000.0
            if (
                sign != self._last_sign
                and 0.0 <= elapsed_ms < self.reversal_window_ms
                and abs(delta) <= 4.0
            ):
                if hasattr(self.metrics, "scroll_jitters_filtered"):
                    self.metrics.scroll_jitters_filtered += 1
                return True
        self._last_sign = sign
        self._last_ts = float(now)
        return False
