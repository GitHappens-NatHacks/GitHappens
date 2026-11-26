"""Opt-in, privacy-preserving keyboard timing telemetry (hold & flight durations only).

Privacy guarantee:
- Key characters, keycodes, and text content are NEVER inspected, logged, hashed, or stored.
- Only anonymous monotonic key-down / key-up timestamps are used to measure hold duration
  (dwell time) and inter-key flight time, which are validated digital biomarkers for
  bradykinesia (slowness of movement) and typing rhythm variability.
"""

from __future__ import annotations

import math
import threading
import time
from collections.abc import Callable
from typing import Any

MIN_HOLD_MS = 10.0
MAX_HOLD_MS = 1200.0
MIN_FLIGHT_MS = 0.0
MAX_FLIGHT_MS = 2000.0


class KeyboardCadenceMonitor:
    """Collects rolling timing-only typing cadence windows when explicitly opted in."""

    def __init__(
        self,
        *,
        window_size: int = 25,
        on_window_ready: Callable[[dict[str, Any]], None] | None = None,
    ):
        self.window_size = max(5, int(window_size))
        self._on_window_ready = on_window_ready
        self._lock = threading.RLock()
        self._enabled = False
        self._listener: Any = None
        self._listener_mode = "disabled"
        self._listener_error: str | None = None

        # Transient active-key map: opaque_slot -> press timestamp (never persisted)
        self._pressed_at: dict[int, float] = {}
        self._last_release_ts: float | None = None

        self._hold_samples_ms: list[float] = []
        self._flight_samples_ms: list[float] = []
        self._burst_timestamps: list[float] = []
        self._latest_window: dict[str, Any] | None = None
        self._total_keystrokes = 0

    @property
    def enabled(self) -> bool:
        with self._lock:
            return self._enabled

    def set_window_callback(self, callback: Callable[[dict[str, Any]], None] | None) -> None:
        with self._lock:
            self._on_window_ready = callback

    def set_enabled(self, enabled: bool, *, attach_os_listener: bool = True) -> None:
        with self._lock:
            want = bool(enabled)
            if want == self._enabled:
                return
            self._enabled = want
            if not want:
                self._stop_listener_locked()
                self._pressed_at.clear()
                self._last_release_ts = None
                self._listener_mode = "disabled"
                self._listener_error = None
            else:
                if attach_os_listener:
                    self._start_listener_locked()
                else:
                    self._listener_mode = "manual_only"

    def stop(self) -> None:
        with self._lock:
            self._enabled = False
            self._stop_listener_locked()
            self._pressed_at.clear()
            self._last_release_ts = None
            self._listener_mode = "disabled"

    def _start_listener_locked(self) -> None:
        self._stop_listener_locked()
        try:
            from pynput import keyboard  # type: ignore[import-untyped]
        except Exception as exc:
            self._listener_mode = "unavailable"
            self._listener_error = f"pynput keyboard listener unavailable: {exc}"
            return

        def _slot(key: Any) -> int:
            # Opaque transient integer slot in memory only; never stored or serialized
            return id(key) if not hasattr(key, "vk") or key.vk is None else int(key.vk)

        def _on_press(key: Any) -> None:
            self.record_timing_event("down", _slot(key), time.monotonic())

        def _on_release(key: Any) -> None:
            self.record_timing_event("up", _slot(key), time.monotonic())

        try:
            listener = keyboard.Listener(on_press=_on_press, on_release=_on_release)
            listener.daemon = True
            listener.start()
            self._listener = listener
            self._listener_mode = "os_timing_only"
            self._listener_error = None
        except Exception as exc:
            self._listener = None
            self._listener_mode = "unavailable"
            self._listener_error = str(exc)

    def _stop_listener_locked(self) -> None:
        listener = self._listener
        self._listener = None
        if listener is not None:
            try:
                listener.stop()
            except Exception:
                pass

    def record_timing_event(
        self,
        event_type: str,
        slot_id: int,
        timestamp: float | None = None,
    ) -> dict[str, Any] | None:
        """Record an anonymous key-down or key-up timestamp. Returns window summary if flushed."""
        now = time.monotonic() if timestamp is None else float(timestamp)
        completed_window: dict[str, Any] | None = None
        cb: Callable[[dict[str, Any]], None] | None = None

        with self._lock:
            if not self._enabled:
                return None

            if event_type == "down":
                # Ignore auto-repeat press events for an already-held slot
                if slot_id in self._pressed_at:
                    return None
                self._pressed_at[slot_id] = now
                if self._last_release_ts is not None:
                    flight_ms = (now - self._last_release_ts) * 1000.0
                    if MIN_FLIGHT_MS <= flight_ms <= MAX_FLIGHT_MS:
                        self._flight_samples_ms.append(flight_ms)
                return None

            if event_type == "up":
                press_ts = self._pressed_at.pop(slot_id, None)
                if press_ts is None:
                    return None
                hold_ms = (now - press_ts) * 1000.0
                self._last_release_ts = now
                if MIN_HOLD_MS <= hold_ms <= MAX_HOLD_MS:
                    self._hold_samples_ms.append(hold_ms)
                    self._burst_timestamps.append(now)
                    self._total_keystrokes += 1

                if len(self._hold_samples_ms) >= self.window_size:
                    completed_window = self._build_window_locked()
                    cb = self._on_window_ready

        if completed_window is not None and cb is not None:
            try:
                cb(completed_window)
            except Exception:
                pass
        return completed_window

    def flush(self) -> dict[str, Any] | None:
        """Flush buffered samples if at least 5 keystrokes were recorded."""
        completed_window: dict[str, Any] | None = None
        cb: Callable[[dict[str, Any]], None] | None = None
        with self._lock:
            if len(self._hold_samples_ms) >= 5:
                completed_window = self._build_window_locked()
                cb = self._on_window_ready
        if completed_window is not None and cb is not None:
            try:
                cb(completed_window)
            except Exception:
                pass
        return completed_window

    def _build_window_locked(self) -> dict[str, Any]:
        holds = list(self._hold_samples_ms)
        flights = list(self._flight_samples_ms)
        stamps = list(self._burst_timestamps)

        self._hold_samples_ms.clear()
        self._flight_samples_ms.clear()
        self._burst_timestamps.clear()

        mean_hold = sum(holds) / len(holds)
        std_hold = math.sqrt(sum((x - mean_hold) ** 2 for x in holds) / len(holds))

        if flights:
            mean_flight = sum(flights) / len(flights)
            std_flight = math.sqrt(sum((x - mean_flight) ** 2 for x in flights) / len(flights))
        else:
            mean_flight = 0.0
            std_flight = 0.0

        # Active burst cadence (excluding inter-burst pauses > 2s)
        active_span_sec = 0.0
        for idx in range(1, len(stamps)):
            gap = stamps[idx] - stamps[idx - 1]
            if 0.0 < gap <= 2.0:
                active_span_sec += gap
        cadence_kpm = (
            round((len(holds) / active_span_sec) * 60.0, 1)
            if active_span_sec >= 0.25
            else 0.0
        )

        # Rhythm regularity score (0-100): lower coefficient of variation = steadier cadence
        hold_cv = std_hold / max(10.0, mean_hold)
        flight_cv = (std_flight / max(20.0, mean_flight)) if mean_flight > 0 else hold_cv
        combined_cv = 0.55 * hold_cv + 0.45 * flight_cv
        regularity_score = round(max(0.0, min(100.0, 100.0 - combined_cv * 85.0)), 2)

        window = {
            "timestamp": time.time(),
            "sample_count": len(holds),
            "mean_hold_ms": round(mean_hold, 2),
            "std_hold_ms": round(std_hold, 2),
            "mean_flight_ms": round(mean_flight, 2),
            "std_flight_ms": round(std_flight, 2),
            "typing_cadence_kpm": cadence_kpm,
            "rhythm_regularity_score": regularity_score,
        }
        self._latest_window = window
        return window

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "enabled": self._enabled,
                "mode": self._listener_mode,
                "error": self._listener_error,
                "total_keystrokes": self._total_keystrokes,
                "buffered_keystrokes": len(self._hold_samples_ms),
                "latest": dict(self._latest_window) if self._latest_window else None,
            }
