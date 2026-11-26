"""Thread-safe SteadyHand background worker for OS tap interception, One Euro filtering, gravity wells, and FFT telemetry."""

from __future__ import annotations

import math
import threading
import time
from typing import Callable

from backend.core.steadyhand.controller import SteadyHandController
from backend.core.steadyhand.displays import detect_displays, display_for_point
from backend.core.steadyhand.exclusions import ActiveAppMonitor
from backend.core.steadyhand.gravity_wells import AccessibilityGravityWells
from backend.core.steadyhand.os_tap import SystemCursorInterceptor


class SteadyHandWorker:
    """Runs SteadyHand filtering, multi-band Welch PSD telemetry, gravity wells, and OS interception."""

    def __init__(
        self,
        controller: SteadyHandController | None = None,
        tick_hz: float = 60.0,
        on_fft_record: Callable[[dict], None] | None = None,
    ):
        self._lock = threading.RLock()
        self.controller = controller or SteadyHandController()
        self.gravity = AccessibilityGravityWells()
        self.app_monitor = ActiveAppMonitor()
        self._interceptor = SystemCursorInterceptor(self._on_tap_event, handle_extended_events=True)
        self._tick_interval = 1.0 / max(1.0, float(tick_hz))
        self._on_fft_record = on_fft_record
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._os_listener_enabled = False
        self._system_mouse_enabled = False
        self._last_injected_pos: tuple[int, int] | None = None
        self._last_injected_at: float = 0.0
        self._last_persisted_sample_time: float | None = None
        self._last_button_pressed = False
        self._active_button: str = "left"
        self._sim_cursor: tuple[float, float] = (500.0, 400.0)

        # Delta-space OS trajectory tracking (prevents recursive feedback attenuation)
        self._virtual_raw_pos: tuple[float, float] | None = None
        self._last_emitted_pos: tuple[float, float] | None = None
        self._last_tap_event_at: float | None = None
        self._was_bypassed = False

        # Everyday convenience modifiers & exclusions
        self.bypass_key: str = "alt"
        self.precision_key: str = "none"
        self._bypass_active = False
        self._precision_active = False
        self._dpi_scale: float = 1.0
        self._last_dpi_check_at: float = 0.0
        self._cached_displays = None

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

    def set_fft_callback(self, callback: Callable[[dict], None] | None) -> None:
        with self._lock:
            self._on_fft_record = callback

    def configure(
        self,
        *,
        enabled: bool | None = None,
        strength: float | None = None,
        min_cutoff: float | None = None,
        beta: float | None = None,
        adaptive_smoothing: bool | None = None,
        simulate_tremor: bool | None = None,
        tremor_intensity: int | None = None,
        anti_drag: bool | None = None,
        anti_drag_threshold_px: float | None = None,
        anti_drag_hold_ms: int | None = None,
        click_freeze_ms: int | None = None,
        click_debounce_ms: int | None = None,
        right_click_guard: bool | None = None,
        scroll_smoothing: bool | None = None,
        gravity_wells: bool | None = None,
        gravity_strength: int | None = None,
        bypass_key: str | None = None,
        precision_key: str | None = None,
        excluded_apps: list[str] | None = None,
    ) -> None:
        with self._lock:
            if enabled is not None:
                self.controller.enabled = bool(enabled)
            if min_cutoff is not None or beta is not None or adaptive_smoothing is not None:
                self.controller.configure_filter(
                    min_cutoff=min_cutoff,
                    beta=beta,
                    adaptive_smoothing=adaptive_smoothing,
                )
            if strength is not None:
                self.controller.strength = float(strength)
            if simulate_tremor is not None:
                self.controller.simulate_tremor = bool(simulate_tremor)
            if tremor_intensity is not None:
                self.controller.tremor_intensity = int(tremor_intensity)
            if anti_drag is not None:
                self.controller.hold.enabled = bool(anti_drag)
            if (
                anti_drag_threshold_px is not None
                or anti_drag_hold_ms is not None
                or click_freeze_ms is not None
            ):
                self.controller.hold.configure(
                    drag_threshold_px=anti_drag_threshold_px,
                    hold_seconds=(anti_drag_hold_ms / 1000.0) if anti_drag_hold_ms is not None else None,
                    click_freeze_ms=click_freeze_ms,
                )
            if click_debounce_ms is not None or right_click_guard is not None:
                self.controller.bounce_guard.configure(
                    click_debounce_ms=click_debounce_ms,
                    right_click_guard=right_click_guard,
                )
            if scroll_smoothing is not None:
                self.controller.scroll_filter.configure(enabled=scroll_smoothing)
            if gravity_wells is not None or gravity_strength is not None:
                self.gravity.configure(
                    enabled=gravity_wells,
                    strength_pct=gravity_strength,
                )
            if bypass_key is not None:
                self.bypass_key = str(bypass_key).strip().lower() or "none"
            if precision_key is not None:
                self.precision_key = str(precision_key).strip().lower() or "none"
            if excluded_apps is not None:
                self.app_monitor.set_excluded_apps(excluded_apps)

    def set_system_mouse(self, enabled: bool, listen_os_mouse: bool = False) -> tuple[bool, str | None]:
        """Enable/disable OS pointer positioning and optional OS event tap."""
        with self._lock:
            if not enabled:
                self.controller.disable_system_mouse()
                self._system_mouse_enabled = False
                self._interceptor.stop()
                self.gravity.stop_prober()
                self._os_listener_enabled = False
                self._virtual_raw_pos = None
                self._last_emitted_pos = None
                self._last_tap_event_at = None
                return False, None

            ok = self.controller.try_enable_system_mouse()
            self._system_mouse_enabled = ok
            if not ok:
                return False, self.controller.last_system_error

            if listen_os_mouse:
                if self.gravity.enabled:
                    self.gravity.start_prober()
                started, err = self._interceptor.start()
                self._os_listener_enabled = started
                if err and not self.controller.last_system_error:
                    self.controller.last_system_error = err
            else:
                self._interceptor.stop()
                self._os_listener_enabled = False
            return True, self.controller.last_system_error

    def _is_echo_move(self, x: float, y: float, now: float) -> bool:
        if self._last_injected_pos is None:
            return False
        if now - self._last_injected_at > 0.05:
            return False
        ix, iy = self._last_injected_pos
        return abs(round(x) - ix) <= 1 and abs(round(y) - iy) <= 1

    def _resolve_dpi_scale(self, x: float, y: float, now: float) -> float:
        if now - self._last_dpi_check_at < 2.0:
            return self._dpi_scale
        self._last_dpi_check_at = now
        try:
            if self._cached_displays is None:
                self._cached_displays = detect_displays()
            disp = display_for_point(x, y, self._cached_displays)
            # On macOS Quartz points are already 1x logical (~96 PPI); on Windows physical px scale by DPI.
            import sys

            if sys.platform.startswith("win"):
                self._dpi_scale = max(1.0, float(disp.scale_factor))
            else:
                self._dpi_scale = 1.0
        except Exception:
            self._dpi_scale = 1.0
        return self._dpi_scale

    def _resolve_delta_space_coords(
        self,
        x: float,
        y: float,
        now: float,
        *,
        in_place_tap: bool,
        precision_active: bool,
    ) -> tuple[float, float]:
        """Reconstruct physical un-warped pointer trajectory from OS deltas."""
        if not in_place_tap:
            self._virtual_raw_pos = (float(x), float(y))
            return float(x), float(y)

        if (
            self._virtual_raw_pos is None
            or self._last_emitted_pos is None
            or self._last_tap_event_at is None
            or (now - self._last_tap_event_at) > 0.5
            or self._was_bypassed
        ):
            self._virtual_raw_pos = (float(x), float(y))
            self._was_bypassed = False
            self._last_tap_event_at = now
            return float(x), float(y)

        dx = float(x) - self._last_emitted_pos[0]
        dy = float(y) - self._last_emitted_pos[1]
        # External pointer warp / monitor jump safeguard
        if math.hypot(dx, dy) > 300.0:
            self._virtual_raw_pos = (float(x), float(y))
            self._last_tap_event_at = now
            return float(x), float(y)

        scale = 0.35 if precision_active else 1.0
        vx = self._virtual_raw_pos[0] + dx * scale
        vy = self._virtual_raw_pos[1] + dy * scale
        self._virtual_raw_pos = (vx, vy)
        self._last_tap_event_at = now
        return vx, vy

    def _on_tap_event(
        self,
        kind: str,
        x: float,
        y: float,
        now: float,
    ) -> tuple[float, float] | str | None:
        in_place_tap = self._interceptor.mode in ("quartz_cgeventtap", "win32_wh_mouse_ll")
        info = self._interceptor.current_event_info
        modifiers = info.get("modifiers") or set()
        button = str(info.get("button") or "left")

        with self._lock:
            if not in_place_tap and kind == "move" and self._is_echo_move(x, y, now):
                return None

            # Check Hold-to-Bypass key or excluded frontmost application
            key_bypass = self.bypass_key != "none" and self.bypass_key in modifiers
            app_excluded = self.app_monitor.matched_rule is not None
            self._bypass_active = bool(key_bypass or app_excluded)
            self._precision_active = bool(
                not self._bypass_active and self.precision_key != "none" and self.precision_key in modifiers
            )

            if self._bypass_active:
                self._was_bypassed = True
                self._last_emitted_pos = (float(x), float(y))
                self._virtual_raw_pos = (float(x), float(y))
                self.controller.hold.anchor = None
                return None

            if kind == "scroll":
                scroll_dy = float(info.get("scroll_dy", 0.0))
                if self.controller.enabled and self.controller.scroll_filter.should_suppress(scroll_dy, now):
                    return "suppress"
                return None

            if kind == "down":
                if self.controller.enabled and not self.controller.bounce_guard.allow_down(button, now):
                    return "suppress"
                raw_x, raw_y = self._resolve_delta_space_coords(
                    x, y, now, in_place_tap=in_place_tap, precision_active=self._precision_active
                )
                self._sim_cursor = (raw_x, raw_y)
                stable = self._process_locked(
                    raw_x, raw_y, now, move_os=False, query_ax=self._system_mouse_enabled
                )
                self._last_button_pressed = True
                self._active_button = button
                self.controller.hold.press(stable, self.controller.last_raw, now)
                self._last_emitted_pos = stable
                return stable if in_place_tap else None

            if kind == "up":
                if self.controller.enabled and not self.controller.bounce_guard.allow_up(button, now):
                    return "suppress"
                raw_x, raw_y = self._resolve_delta_space_coords(
                    x, y, now, in_place_tap=in_place_tap, precision_active=self._precision_active
                )
                self._sim_cursor = (raw_x, raw_y)
                stable = self._process_locked(
                    raw_x, raw_y, now, move_os=False, query_ax=self._system_mouse_enabled
                )
                if self._last_button_pressed:
                    self._last_button_pressed = False
                    anchor = self.controller.hold.anchor
                    slipped = (
                        anchor is not None
                        and math.dist(self.controller.last_raw, anchor) >= self.controller.hold.drag_threshold_px
                    )
                    stable = self.controller.hold.release(stable, slipped=slipped)
                self._last_emitted_pos = stable
                return stable if in_place_tap else None

            if kind == "move":
                raw_x, raw_y = self._resolve_delta_space_coords(
                    x, y, now, in_place_tap=in_place_tap, precision_active=self._precision_active
                )
                self._sim_cursor = (raw_x, raw_y)
                stable = self._process_locked(
                    raw_x,
                    raw_y,
                    now,
                    move_os=(self._system_mouse_enabled and not in_place_tap),
                    query_ax=self._system_mouse_enabled,
                )
                self._last_emitted_pos = stable
                return stable if in_place_tap else None

            return None

    def process_sample(
        self,
        x: float,
        y: float,
        timestamp: float | None = None,
        pressed: bool | None = None,
    ) -> dict:
        """Feed a pointer sample directly (used by simulation, sandbox, or API sample injection)."""
        now = time.perf_counter() if timestamp is None else float(timestamp)
        with self._lock:
            self._sim_cursor = (float(x), float(y))
            stable = self._process_locked(
                x,
                y,
                now,
                move_os=self._system_mouse_enabled,
                query_ax=False,
            )
            if pressed is True and not self._last_button_pressed:
                self._last_button_pressed = True
                self.controller.hold.press(stable, self.controller.last_raw, now)
            elif pressed is False and self._last_button_pressed:
                self._last_button_pressed = False
                anchor = self.controller.hold.anchor
                slipped = (
                    anchor is not None
                    and math.dist(self.controller.last_raw, anchor) >= self.controller.hold.drag_threshold_px
                )
                stable = self.controller.hold.release(stable, slipped=slipped)
            self._emit_fft_if_ready()
            return self.snapshot()

    def _process_locked(
        self,
        x: float,
        y: float,
        now: float,
        *,
        move_os: bool,
        query_ax: bool,
    ) -> tuple[float, float]:
        dpi_scale = self._resolve_dpi_scale(x, y, now)
        stable = self.controller.stabilize(x, y, now, dpi_scale=dpi_scale)
        if self.controller.hold.anchor is not None:
            stable = self.controller.hold.move(stable, self.controller.last_raw, now)
        elif query_ax and self.controller.enabled:
            stable = self.gravity.apply_pull(stable[0], stable[1], now)
            self.controller.last_stable = stable

        if move_os and self._system_mouse_enabled:
            rx, ry = round(stable[0]), round(stable[1])
            self._last_injected_pos = (rx, ry)
            self._last_injected_at = now
            self.controller.move_system_pointer(rx, ry)
        return stable

    def _emit_fft_if_ready(self) -> None:
        if self._on_fft_record is None:
            return
        record = self.consume_latest_fft_record()
        if record is not None:
            try:
                self._on_fft_record(record)
            except Exception:
                pass

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
            self._interceptor.stop()
            self.gravity.stop_prober()
            self.app_monitor.stop()
            self._os_listener_enabled = False
            thread = self._thread
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=timeout)
        with self._lock:
            if self._thread is thread and (thread is None or not thread.is_alive()):
                self._thread = None

    def _run_loop(self) -> None:
        last_flush = time.perf_counter()
        while not self._stop_event.is_set():
            start = time.perf_counter()
            with self._lock:
                if self.controller.simulate_tremor:
                    cx, cy = self._sim_cursor
                    self._process_locked(
                        cx,
                        cy,
                        start,
                        move_os=self._system_mouse_enabled,
                        query_ax=False,
                    )
                if start - last_flush >= 0.45:
                    last_flush = start
                    self._emit_fft_if_ready()
            elapsed = time.perf_counter() - start
            sleep_s = max(0.001, self._tick_interval - elapsed)
            self._stop_event.wait(sleep_s)

    def stability_score(self) -> float:
        """Return a 0-100 stability score from broadband tremor power, RMS amplitude, and suppression."""
        with self._lock:
            latest = self.controller.telemetry.latest
            if latest is None:
                return round(self.controller.telemetry.last_valid_score, 2)
            tremor_idx = float(latest.get("tremor_index", 0.0))
            rms_px = float(latest.get("rms_amplitude_px", 0.0))
            suppression = float(latest.get("suppression_ratio", 0.0))
            score = 100.0 - tremor_idx * 0.72 - min(25.0, rms_px * 0.55)
            if self.controller.enabled and suppression > 0.0:
                score += suppression * min(35.0, tremor_idx * 0.45 + min(15.0, rms_px * 0.35))
            clamped = round(max(0.0, min(100.0, score)), 2)
            self.controller.telemetry.last_valid_score = clamped
            return clamped

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
                "click_rescues": self.controller.telemetry.slip_clicks_rescued,
                "drags_prevented": self.controller.telemetry.spastic_drags_prevented,
                "bounces_blocked": self.controller.telemetry.double_clicks_blocked,
            }

    def snapshot(self) -> dict:
        with self._lock:
            latest = self.controller.telemetry.latest
            grav = self.gravity.snapshot()
            return {
                "running": self.running,
                "stabilization_active": self.controller.enabled,
                "strength": round(self.controller.strength, 3),
                "simulate_tremor": self.controller.simulate_tremor,
                "tremor_intensity": self.controller.tremor_intensity,
                "tremor_hz": latest["dominant_hz"] if latest else None,
                "tremor_index": latest["tremor_index"] if latest else 0.0,
                "resting_band_pct": latest["resting_band_pct"] if latest else 0.0,
                "action_band_pct": latest["action_band_pct"] if latest else 0.0,
                "rms_amplitude_px": latest["rms_amplitude_px"] if latest else 0.0,
                "rms_amplitude_mm": latest["rms_amplitude_mm"] if latest else 0.0,
                "tremor_severity": latest["tremor_severity"] if latest else "minimal",
                "medication_state_estimate": (
                    latest["medication_state_estimate"] if latest else None
                ),
                "stability_score": self.stability_score(),
                "raw_pos": list(self.controller.last_raw),
                "stable_pos": list(self.controller.last_stable),
                "spastic_drags_prevented": self.controller.telemetry.spastic_drags_prevented,
                "slip_clicks_rescued": self.controller.telemetry.slip_clicks_rescued,
                "double_clicks_blocked": self.controller.telemetry.double_clicks_blocked,
                "scroll_jitters_filtered": self.controller.telemetry.scroll_jitters_filtered,
                "click_freeze_active": self.controller.hold.click_freeze_active,
                "gravity_well_active": grav["gravity_well_active"],
                "gravity_target_role": grav["gravity_target_role"],
                "bypass_active": self._bypass_active,
                "precision_active": self._precision_active,
                "excluded_app_active": self.app_monitor.matched_rule,
                "system_mouse_enabled": self._system_mouse_enabled,
                "os_listener_enabled": self._os_listener_enabled,
                "os_tap_mode": self._interceptor.mode,
                "os_tap_error": self._interceptor.last_error or self.controller.last_system_error,
                "last_system_error": self.controller.last_system_error,
            }
