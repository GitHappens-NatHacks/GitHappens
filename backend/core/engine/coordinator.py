"""Thread-safe engine coordinator binding SteadyHand, Sandbox Lab, Gaze, Speech, and SQLite."""

from __future__ import annotations

import threading
import time
import uuid
from collections.abc import Callable
from typing import Any

from backend.core.engine.profiles import ModuleFlags, Profile, get_profile
from backend.core.engine.settings import AccessibilitySettings
from backend.core.gaze.calibration import (
    HEAD_POSES,
    GazeCalibration,
    Point,
    head_calibration,
)
from backend.core.gaze.controller import GazeController, ScreenRect
from backend.core.steadyhand.checkin import evaluate_motor_checkin
from backend.core.steadyhand.keyboard_cadence import KeyboardCadenceMonitor
from backend.core.steadyhand.resting_hand import (
    run_webcam_resting_check,
    score_resting_hand_samples,
)
from backend.core.steadyhand.worker import SteadyHandWorker
from backend.db.database import Database


class AdaptiveEngine:
    """Qt-free accessibility profile coordinator."""

    def __init__(self):
        self._lock = threading.RLock()
        self._profile: Profile = get_profile("parkinsons")
        self._profile_listeners: list[Callable[[str], None]] = []
        self._module_listeners: list[Callable[[ModuleFlags], None]] = []

    @property
    def profile(self) -> Profile:
        with self._lock:
            return self._profile

    @property
    def modules(self) -> ModuleFlags:
        with self._lock:
            return self._profile.modules

    def set_profile(self, profile_id: str) -> None:
        with self._lock:
            self._profile = get_profile(profile_id)
            pid = self._profile.id
            mods = self._profile.modules
        for cb in self._profile_listeners:
            cb(pid)
        for cb in self._module_listeners:
            cb(mods)

    def set_module(self, name: str, enabled: bool) -> None:
        with self._lock:
            if not hasattr(self._profile.modules, name):
                raise AttributeError(f"Unknown module flag: {name}")
            setattr(self._profile.modules, name, bool(enabled))
            mods = self._profile.modules
        for cb in self._module_listeners:
            cb(mods)


class EngineCoordinator:
    """Top-level service coordinating workers, settings, calibration, and telemetry."""

    def __init__(
        self,
        db: Database | None = None,
        gaze_controller: GazeController | None = None,
        steady_worker: SteadyHandWorker | None = None,
        auto_start_workers: bool = True,
    ):
        self._lock = threading.RLock()
        self.session_id = str(uuid.uuid4())
        self.db = db or Database()
        self.adaptive = AdaptiveEngine()
        self.settings = self.db.load_settings()

        # Always keep camera gaze tracking off on startup; optionally resume pointer smoothing if opted in.
        boot_updates: dict[str, Any] = {}
        if self.settings.gaze_control:
            boot_updates["gaze_control"] = False
        if self.settings.system_mouse and not self.settings.resume_stabilization_on_launch:
            boot_updates["system_mouse"] = False
        if boot_updates:
            self.settings = self.db.save_settings(
                AccessibilitySettings.from_dict({**self.settings.as_dict(), **boot_updates})
            )

        self.steady_worker = steady_worker or SteadyHandWorker()
        self.steady_worker.set_fft_callback(self._persist_fft_record)

        # Isolated worker for local canvas sandbox / practice strip (never touches OS cursor or DB).
        self.sandbox_worker = SteadyHandWorker(tick_hz=60.0)

        # Opt-in timing-only keyboard cadence monitor (never inspects or stores key characters).
        self.keyboard_monitor = KeyboardCadenceMonitor(
            on_window_ready=self._persist_keyboard_cadence
        )

        self.gaze_controller = gaze_controller or GazeController(
            screen_rect=ScreenRect(
                0, 0, self.settings.screen_width, self.settings.screen_height
            ),
            on_exit_requested=self.emergency_stop_gaze,
        )

        self._cached_displays: list[Any] | None = None
        self._cached_screen_dims: tuple[int, int] | None = None

        self._restore_calibration()
        self.apply_settings(self.settings, persist=False)
        if auto_start_workers:
            self.steady_worker.start()

    def _restore_calibration(self) -> None:
        active = self.db.get_active_calibration(self.settings.gaze_source)
        if active is None:
            return
        try:
            cal = GazeCalibration.from_dict(active["calibration"])
            self.gaze_controller.set_calibration(cal, active["error_px"])
            if active["open_ears"]:
                self.gaze_controller.calibrate_blink(active["open_ears"])
        except Exception:
            pass

    def _resolve_screen_rect(self, width: int, height: int) -> ScreenRect:
        from backend.core.steadyhand.displays import detect_displays, virtual_screen_rect

        dims = (int(width), int(height))
        if self._cached_displays is None or self._cached_screen_dims != dims:
            self._cached_displays = detect_displays(width, height)
            self._cached_screen_dims = dims

        displays = self._cached_displays
        if len(displays) > 1 or any(d.left != 0 or d.top != 0 for d in displays):
            return virtual_screen_rect(
                displays,
                fallback_width=width,
                fallback_height=height,
            )
        return ScreenRect(0, 0, width, height)

    def apply_settings(
        self,
        new_settings: AccessibilitySettings,
        *,
        persist: bool = True,
    ) -> AccessibilitySettings:
        with self._lock:
            validated = new_settings.validated()
            if persist:
                validated = self.db.save_settings(validated)
            self.settings = validated

            self.adaptive.set_profile(validated.profile)
            self.adaptive.set_module("gaze_control", validated.gaze_control)
            self.adaptive.set_module("steady_hand", validated.steady_hand)
            self.adaptive.set_module("smart_interface", validated.smart_interface)
            self.adaptive.set_module("predictive_speech", validated.predictive_speech)

            effective_steady = validated.assistance_enabled and validated.steady_hand
            shared_cfg = dict(
                enabled=effective_steady,
                strength=validated.tremor_strength / 100.0,
                min_cutoff=validated.one_euro_min_cutoff,
                beta=validated.one_euro_beta,
                adaptive_smoothing=validated.adaptive_smoothing,
                simulate_tremor=validated.simulate_tremor,
                tremor_intensity=validated.tremor_intensity,
                anti_drag=validated.anti_drag,
                anti_drag_threshold_px=validated.anti_drag_threshold_px,
                anti_drag_hold_ms=validated.anti_drag_hold_ms,
                click_freeze_ms=validated.click_freeze_ms,
                click_debounce_ms=validated.click_debounce_ms,
                right_click_guard=validated.right_click_guard,
                scroll_smoothing=validated.scroll_smoothing,
                gravity_wells=validated.gravity_wells,
                gravity_strength=validated.gravity_strength,
                bypass_key=validated.bypass_key,
                precision_key=validated.precision_key,
            )
            self.steady_worker.configure(
                **shared_cfg,
                excluded_apps=validated.excluded_apps,
            )
            self.sandbox_worker.configure(**{**shared_cfg, "gravity_wells": False})

            self.steady_worker.set_system_mouse(
                enabled=validated.system_mouse and effective_steady,
                listen_os_mouse=validated.system_mouse and effective_steady,
            )
            self.keyboard_monitor.set_enabled(validated.keyboard_cadence_telemetry)

            if self.gaze_controller.source != validated.gaze_source:
                self.gaze_controller.set_source(validated.gaze_source)
                self._restore_calibration()

            screen_rect = self._resolve_screen_rect(
                validated.screen_width, validated.screen_height
            )
            self.gaze_controller.set_screen_rect(screen_rect)
            self.gaze_controller.set_dwell_ms(validated.gaze_dwell_ms)
            self.gaze_controller.blink_select = validated.blink_select
            self.gaze_controller.set_system_mouse(
                validated.system_mouse and validated.assistance_enabled and validated.gaze_control
            )
            return validated

    def update_settings(self, updates: dict[str, Any]) -> AccessibilitySettings:
        with self._lock:
            current = self.settings.as_dict()
            current.update({k: v for k, v in updates.items() if v is not None})
            return self.apply_settings(AccessibilitySettings.from_dict(current), persist=True)

    def toggle(
        self,
        *,
        assistance_enabled: bool | None = None,
        steady_hand: bool | None = None,
        gaze_control: bool | None = None,
        simulate_tremor: bool | None = None,
        system_mouse: bool | None = None,
        camera: bool | None = None,
        camera_index: int = 0,
    ) -> dict[str, Any]:
        with self._lock:
            updates: dict[str, Any] = {}
            if assistance_enabled is not None:
                updates["assistance_enabled"] = bool(assistance_enabled)
            if steady_hand is not None:
                updates["steady_hand"] = bool(steady_hand)
            if gaze_control is not None:
                updates["gaze_control"] = bool(gaze_control)
            if simulate_tremor is not None:
                updates["simulate_tremor"] = bool(simulate_tremor)
            if system_mouse is not None:
                updates["system_mouse"] = bool(system_mouse)

            if updates:
                self.update_settings(updates)

            camera_started = self.gaze_controller.running
            if camera is True:
                camera_started = self.gaze_controller.start(
                    camera_index=camera_index,
                    preview=True,
                )
            elif camera is False:
                self.gaze_controller.stop()
                camera_started = False

            return {
                "settings": self.settings.as_dict(),
                "camera_running": camera_started,
                "steadyhand_running": self.steady_worker.running,
            }

    def emergency_stop_gaze(self) -> dict[str, Any]:
        """Immediately stop camera tracking, disable gaze_control, and release system mouse."""
        with self._lock:
            self.gaze_controller.paused = False
            self.gaze_controller.stop()
            self.gaze_controller.set_system_mouse(False)
            self.update_settings({"gaze_control": False, "system_mouse": False})
            return {
                "settings": self.settings.as_dict(),
                "camera_running": False,
                "steadyhand_running": self.steady_worker.running,
            }

    def stop_gaze_on_disconnect(self) -> dict[str, Any]:
        """Stop camera when UI closes/minimizes, keeping SteadyHand tray stabilization active."""
        with self._lock:
            self.gaze_controller.paused = False
            self.gaze_controller.stop()
            self.gaze_controller.set_system_mouse(False)
            if self.settings.gaze_control:
                updates: dict[str, Any] = {"gaze_control": False}
                if not self.settings.steady_hand:
                    updates["system_mouse"] = False
                self.update_settings(updates)
            return {
                "settings": self.settings.as_dict(),
                "camera_running": False,
                "steadyhand_running": self.steady_worker.running,
            }

    def emergency_stop_all(self) -> dict[str, Any]:
        """Global emergency stop: halts GazeCam and releases OS pointer interception."""
        with self._lock:
            self.gaze_controller.paused = False
            self.gaze_controller.stop()
            self.gaze_controller.set_system_mouse(False)
            self.update_settings({"gaze_control": False, "system_mouse": False})
            return {
                "settings": self.settings.as_dict(),
                "camera_running": False,
                "steadyhand_running": self.steady_worker.running,
            }

    def pause_gaze(self, paused: bool) -> dict[str, Any]:
        """Freeze gaze dwell/cursor output while keeping live raw landmarks flowing (for calibration)."""
        with self._lock:
            self.gaze_controller.paused = bool(paused)
            return {"paused": self.gaze_controller.paused}

    def clear_calibration(self) -> dict[str, Any]:
        """Clear in-memory and active SQLite calibration for the current gaze source."""
        with self._lock:
            source = self.gaze_controller.source
            self.gaze_controller.clear_calibration()
            self.db.deactivate_calibration(source)
            return {"calibrated": False, "source": source}

    def calibrate_dots(
        self,
        *,
        source: str,
        features: list[Point],
        targets: list[Point],
        open_ears: list[float] | None = None,
        profile_name: str = "default",
    ) -> dict[str, Any]:
        with self._lock:
            if source != self.gaze_controller.source:
                self.gaze_controller.set_source(source)
                self.update_settings({"gaze_source": source})
            cal = GazeCalibration()
            cal.fit(features, targets)
            err = cal.error_px(features, targets)
            self.gaze_controller.set_calibration(cal, err)
            if open_ears:
                self.gaze_controller.calibrate_blink(open_ears)
            profile_id = self.db.save_calibration_profile(
                name=profile_name,
                source=source,
                calibration_dict=cal.to_dict(),
                error_px=err,
                open_ears=open_ears,
                activate=True,
            )
            return {
                "profile_id": profile_id,
                "source": source,
                "error_px": round(err, 2),
                "calibrated": True,
            }

    def calibrate_head_poses(
        self,
        *,
        poses: dict[str, Point],
        open_ears: list[float] | None = None,
        profile_name: str = "head-default",
    ) -> dict[str, Any]:
        missing = [k for k in HEAD_POSES if k not in poses]
        if missing:
            raise ValueError(f"Missing head poses: {missing}")
        with self._lock:
            if self.gaze_controller.source != "head":
                self.gaze_controller.set_source("head")
                self.update_settings({"gaze_source": "head"})
            size = (float(self.settings.screen_width), float(self.settings.screen_height))
            cal = head_calibration(poses, size)
            err = 40.0
            self.gaze_controller.set_calibration(cal, err)
            if open_ears:
                self.gaze_controller.calibrate_blink(open_ears)
            profile_id = self.db.save_calibration_profile(
                name=profile_name,
                source="head",
                calibration_dict=cal.to_dict(),
                error_px=err,
                open_ears=open_ears,
                activate=True,
            )
            return {
                "profile_id": profile_id,
                "source": "head",
                "error_px": err,
                "calibrated": True,
            }

    def _persist_fft_record(self, record: dict) -> None:
        self.db.record_tremor_sample(
            session_id=self.session_id,
            timestamp=record["timestamp"],
            sample_time=record["sample_time"],
            tremor_index=record["tremor_index"],
            dominant_hz=record["dominant_hz"],
            stability_score=record["stability_score"],
            medication_state_estimate=record["medication_state_estimate"],
            stabilization_active=record["stabilization_active"],
            simulated=record["simulated"],
            resting_band_pct=record.get("resting_band_pct", 0.0),
            action_band_pct=record.get("action_band_pct", 0.0),
            rms_amplitude_px=record.get("rms_amplitude_px", 0.0),
            rms_amplitude_mm=record.get("rms_amplitude_mm", 0.0),
            click_rescues=record.get("click_rescues", 0),
            drags_prevented=record.get("drags_prevented", 0),
            bounces_blocked=record.get("bounces_blocked", 0),
            preset_name=self.settings.profile,
        )

    def _persist_keyboard_cadence(self, window: dict[str, Any]) -> None:
        self.db.record_keyboard_cadence(session_id=self.session_id, window=window)

    def record_motor_checkin(
        self,
        *,
        hold_samples: list[dict[str, float]],
        target_x: float,
        target_y: float,
        taps: list[dict[str, float]] | None = None,
        tap_hit_radius_px: float = 28.0,
        context_tag: str = "routine",
        notes: str = "",
    ) -> dict[str, Any]:
        scored = evaluate_motor_checkin(
            hold_samples=hold_samples,
            target_x=target_x,
            target_y=target_y,
            taps=taps,
            tap_hit_radius_px=tap_hit_radius_px,
            context_tag=context_tag,
            notes=notes,
        )
        return self.db.record_motor_checkin(session_id=self.session_id, scored=scored)

    def record_resting_hand_checkin(
        self,
        *,
        mode: str = "webcam",
        samples: list[dict[str, float]] | None = None,
        duration_sec: float = 10.0,
        camera_index: int = 0,
        prefer_backend: str = "auto",
        context_tag: str = "resting_hand",
        notes: str = "",
    ) -> dict[str, Any]:
        if mode == "samples":
            if not samples:
                raise ValueError("samples list is required when mode='samples'.")
            scored = score_resting_hand_samples(
                samples,
                backend_used="opencv_optical_flow" if prefer_backend == "opencv" else "client_samples",
                context_tag=context_tag,
                notes=notes,
            )
        else:
            scored = run_webcam_resting_check(
                duration_sec=duration_sec,
                camera_index=camera_index,
                prefer_backend=prefer_backend,  # type: ignore[arg-type]
                context_tag=context_tag,
                notes=notes,
            )
        return self.db.record_motor_checkin(session_id=self.session_id, scored=scored)

    def persist_pending_fft(self) -> dict | None:
        record = self.steady_worker.consume_latest_fft_record()
        if record is None:
            return None
        self._persist_fft_record(record)
        return record

    def telemetry_snapshot(self) -> dict[str, Any]:
        self.persist_pending_fft()
        steady = self.steady_worker.snapshot()
        gaze = self.gaze_controller.snapshot()
        with self._lock:
            s = self.settings
            return {
                "timestamp": time.time(),
                "session_id": self.session_id,
                "tremor_hz": steady["tremor_hz"],
                "tremor_index": steady["tremor_index"],
                "resting_band_pct": steady["resting_band_pct"],
                "action_band_pct": steady["action_band_pct"],
                "rms_amplitude_px": steady["rms_amplitude_px"],
                "rms_amplitude_mm": steady["rms_amplitude_mm"],
                "tremor_severity": steady["tremor_severity"],
                "stabilization_active": steady["stabilization_active"],
                "stability_score": steady["stability_score"],
                "medication_state_estimate": steady["medication_state_estimate"],
                "gaze": {
                    "x": gaze["x"],
                    "y": gaze["y"],
                    "raw_feature": gaze["raw_feature"],
                    "ear": gaze["ear"],
                    "face_detected": gaze["face_detected"],
                    "dwell_progress": gaze["dwell_progress"],
                    "blink": gaze["blink"],
                    "source": gaze["source"],
                    "status": gaze["status"],
                    "calibrated": gaze["calibrated"],
                    "target_id": gaze["target_id"],
                    "running": gaze["running"],
                    "lighting_quality": gaze.get("lighting_quality", "ok"),
                    "luma": gaze.get("luma"),
                },
                "steadyhand": {
                    "raw_pos": steady["raw_pos"],
                    "stable_pos": steady["stable_pos"],
                    "strength": steady["strength"],
                    "simulate_tremor": steady["simulate_tremor"],
                    "tremor_intensity": steady["tremor_intensity"],
                    "spastic_drags_prevented": steady["spastic_drags_prevented"],
                    "slip_clicks_rescued": steady["slip_clicks_rescued"],
                    "double_clicks_blocked": steady["double_clicks_blocked"],
                    "scroll_jitters_filtered": steady["scroll_jitters_filtered"],
                    "click_freeze_active": steady["click_freeze_active"],
                    "gravity_well_active": steady["gravity_well_active"],
                    "gravity_target_role": steady["gravity_target_role"],
                    "bypass_active": steady["bypass_active"],
                    "precision_active": steady["precision_active"],
                    "excluded_app_active": steady["excluded_app_active"],
                    "os_tap_mode": steady["os_tap_mode"],
                    "os_tap_error": steady["os_tap_error"],
                    "system_mouse_enabled": steady["system_mouse_enabled"],
                },
                "active_modes": {
                    "profile": s.profile,
                    "assistance_enabled": s.assistance_enabled,
                    "steady_hand": s.steady_hand,
                    "gaze_control": s.gaze_control,
                    "smart_interface": s.smart_interface,
                    "predictive_speech": s.predictive_speech,
                    "simulate_tremor": s.simulate_tremor,
                    "keyboard_cadence_telemetry": s.keyboard_cadence_telemetry,
                },
                "keyboard_cadence": self.keyboard_monitor.snapshot(),
            }

    def shutdown(self) -> None:
        self.gaze_controller.stop()
        self.steady_worker.stop()
        self.sandbox_worker.stop()
        self.keyboard_monitor.flush()
        self.keyboard_monitor.stop()
        self.db.close()
