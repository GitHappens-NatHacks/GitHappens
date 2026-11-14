"""Thread-safe SteadyHand background worker for mouse capture, One-Euro filtering, and FFT telemetry."""

from __future__ import annotations

import math
import threading
import time

from backend.core.steadyhand.controller import SteadyHandController


class SteadyHandWorker:
    """Runs SteadyHand filtering, 4-7 Hz FFT tremor estimation, and optional OS mouse capture."""

    def __init__(self, controller: SteadyHandController | None = None, tick_hz: float = 60.0):
        self._lock = threading.RLock()
        self.controller = controller or SteadyHandController()
        self._tick_interval = 1.0 / max(1.0, float(tick_hz))
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._mouse_listener = None
        self._os_listener_enabled = False
        self._system_mouse_enabled = False
        self._last_injected_pos: tuple[int, int] | None = None
        self._last_injected_at: float = 0.0
        self._last_persisted_sample_time: float | None = None
        self._last_button_pressed = False
        self._sim_cursor: tuple[float, float] = (500.0, 400.0)

    @property
    def running(self) -> bool:
        with self._lock:
            return self._thread is not None and self._thread.is_alive()

    @property
    def os_listener_enabled(self) -> bool:
        with self._lock:
            return self._os_listener_enabled

    @property
    def system_mouse_enabled(self) -> bool:
        with self._lock:
            return self._system_mouse_enabled

    def configure(
        self,
        *,
        enabled: bool | None = None,
        strength: float | None = None,
        min_cutoff: float | None = None,
        beta: float | None = None,
        simulate_tremor: bool | None = None,
        tremor_intensity: int | None = None,
        anti_drag: bool | None = None,
        anti_drag_threshold_px: float | None = None,
        anti_drag_hold_ms: int | None = None,
    ) -> None:
        with self._lock:
            if enabled is not None:
                self.controller.enabled = bool(enabled)
            if min_cutoff is not None or beta is not None:
                self.controller.configure_filter(min_cutoff=min_cutoff, beta=beta)
            if strength is not None:
                self.controller.strength = float(strength)
            if simulate_tremor is not None:
                self.controller.simulate_tremor = bool(simulate_tremor)
            if tremor_intensity is not None:
                self.controller.tremor_intensity = int(tremor_intensity)
            if anti_drag is not None:
                self.controller.hold.enabled = bool(anti_drag)
            if anti_drag_threshold_px is not None or anti_drag_hold_ms is not None:
                self.controller.hold.configure(
                    drag_threshold_px=anti_drag_threshold_px,
                    hold_seconds=(anti_drag_hold_ms / 1000.0) if anti_drag_hold_ms is not None else None,
                )

    def set_system_mouse(self, enabled: bool, listen_os_mouse: bool = False) -> tuple[bool, str | None]:
        """Enable/disable OS pointer positioning and optional global mouse listener."""
        with self._lock:
            if not enabled:
                self.controller.disable_system_mouse()
                self._system_mouse_enabled = False
                self._stop_mouse_listener()
                return False, None

            ok = self.controller.try_enable_system_mouse()
            self._system_mouse_enabled = ok
            if not ok:
                return False, self.controller.last_system_error

            if listen_os_mouse:
                self._start_mouse_listener()
            else:
                self._stop_mouse_listener()
            return True, None

    def _start_mouse_listener(self) -> None:
        if self._mouse_listener is not None:
            return
        try:
            from pynput import mouse

            def on_move(x: float, y: float) -> None:
                self._on_os_move(x, y)

            def on_click(x: float, y: float, button, pressed: bool) -> None:
                if getattr(button, "name", "") == "left":
                    self._on_os_click(x, y, pressed)

            listener = mouse.Listener(on_move=on_move, on_click=on_click)
            listener.daemon = True
            listener.start()
            self._mouse_listener = listener
            self._os_listener_enabled = True
        except Exception as exc:
            self.controller.last_system_error = str(exc)
            self._mouse_listener = None
            self._os_listener_enabled = False

    def _stop_mouse_listener(self) -> None:
        listener = self._mouse_listener
        self._mouse_listener = None
        self._os_listener_enabled = False
        if listener is not None:
            try:
                listener.stop()
            except Exception:
                pass

    def _is_echo_move(self, x: float, y: float, now: float) -> bool:
        if self._last_injected_pos is None:
            return False
        if now - self._last_injected_at > 0.05:
            return False
        ix, iy = self._last_injected_pos
        return abs(round(x) - ix) <= 1 and abs(round(y) - iy) <= 1

    def _on_os_move(self, x: float, y: float) -> None:
        now = time.perf_counter()
        with self._lock:
            if self._is_echo_move(x, y, now):
                return
            self._sim_cursor = (float(x), float(y))
            self._process_locked(x, y, now, move_os=self._system_mouse_enabled)

    def _on_os_click(self, x: float, y: float, pressed: bool) -> None:
        now = time.perf_counter()
        with self._lock:
            self._sim_cursor = (float(x), float(y))
            stable = self._process_locked(x, y, now, move_os=False)
            if pressed:
                self._last_button_pressed = True
                self.controller.hold.press(stable, self.controller.last_raw, now)
            elif self._last_button_pressed:
                self._last_button_pressed = False
                self.controller.hold.release(stable, slipped=False)

    def process_sample(
        self,
        x: float,
        y: float,
        timestamp: float | None = None,
        pressed: bool | None = None,
    ) -> dict:
        """Feed a pointer sample directly (used by simulation or API sample injection)."""
        now = time.perf_counter() if timestamp is None else float(timestamp)
        with self._lock:
            self._sim_cursor = (float(x), float(y))
            stable = self._process_locked(x, y, now, move_os=self._system_mouse_enabled)
            if pressed is True and not self._last_button_pressed:
                self._last_button_pressed = True
                self.controller.hold.press(stable, self.controller.last_raw, now)
            elif pressed is False and self._last_button_pressed:
                self._last_button_pressed = False
                stable = self.controller.hold.release(stable, slipped=False)
            return self.snapshot()

    def _process_locked(self, x: float, y: float, now: float, move_os: bool) -> tuple[float, float]:
        stable = self.controller.stabilize(x, y, now)
        if self.controller.hold.anchor is not None:
            stable = self.controller.hold.move(stable, self.controller.last_raw, now)
        if move_os and self._system_mouse_enabled:
            rx, ry = round(stable[0]), round(stable[1])
            self._last_injected_pos = (rx, ry)
            self._last_injected_at = now
            self.controller.move_system_pointer(rx, ry)
        return stable

    def start(self) -> bool:
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return True
            self._stop_event.clear()
            self._thread = threading.Thread(
                target=self._run_loop,
                name="steadyhand-worker",
                daemon=True,
            )
            self._thread.start()
            return True

    def stop(self, timeout: float = 2.0) -> None:
        self._stop_event.set()
        with self._lock:
            self._stop_mouse_listener()
            thread = self._thread
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=timeout)
        with self._lock:
            if self._thread is thread and (thread is None or not thread.is_alive()):
                self._thread = None

    def _run_loop(self) -> None:
        while not self._stop_event.is_set():
            start = time.perf_counter()
            with self._lock:
                if self.controller.simulate_tremor:
                    cx, cy = self._sim_cursor
                    self._process_locked(cx, cy, start, move_os=self._system_mouse_enabled)
            elapsed = time.perf_counter() - start
            sleep_s = max(0.001, self._tick_interval - elapsed)
            self._stop_event.wait(sleep_s)

    def stability_score(self) -> float:
        """Return a 0-100 stability score combining tremor index and stabilization state."""
        with self._lock:
            latest = self.controller.telemetry.latest
            if latest is None:
                return 100.0
            tremor_idx = float(latest.get("tremor_index", 0.0))
            raw_x, raw_y = self.controller.last_raw
            stable_x, stable_y = self.controller.last_stable
            damping_bonus = 0.0
            if self.controller.enabled:
                offset = math.hypot(raw_x - stable_x, raw_y - stable_y)
                damping_bonus = min(20.0, offset * 0.4)
            return round(max(0.0, min(100.0, (100.0 - tremor_idx) + damping_bonus)), 2)

    def consume_latest_fft_record(self) -> dict | None:
        """Return the latest FFT record once when a new 0.5 s window is computed."""
        with self._lock:
            latest = self.controller.telemetry.latest
            if latest is None:
                return None
            sample_time = latest.get("sample_time")
            if sample_time == self._last_persisted_sample_time:
                return None
            self._last_persisted_sample_time = sample_time
            return {
                **latest,
                "stability_score": self.stability_score(),
                "stabilization_active": self.controller.enabled,
            }

    def snapshot(self) -> dict:
        with self._lock:
            latest = self.controller.telemetry.latest
            return {
                "running": self.running,
                "stabilization_active": self.controller.enabled,
                "strength": round(self.controller.strength, 3),
                "simulate_tremor": self.controller.simulate_tremor,
                "tremor_intensity": self.controller.tremor_intensity,
                "tremor_hz": latest["dominant_hz"] if latest else None,
                "tremor_index": latest["tremor_index"] if latest else 0.0,
                "medication_state_estimate": (
                    latest["medication_state_estimate"] if latest else None
                ),
                "stability_score": self.stability_score(),
                "raw_pos": list(self.controller.last_raw),
                "stable_pos": list(self.controller.last_stable),
                "spastic_drags_prevented": self.controller.telemetry.spastic_drags_prevented,
                "slip_clicks_rescued": self.controller.telemetry.slip_clicks_rescued,
                "system_mouse_enabled": self._system_mouse_enabled,
                "os_listener_enabled": self._os_listener_enabled,
                "last_system_error": self.controller.last_system_error,
            }
