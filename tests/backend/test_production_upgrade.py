"""Production upgrade tests: delta-space smoothing, bounce/scroll guards, multi-band PSD, auth, and clinical diary."""

from __future__ import annotations

import math
import time

import pytest
from fastapi.testclient import TestClient

from backend.api.main import create_app
from backend.core.engine.coordinator import EngineCoordinator
from backend.core.steadyhand.exclusions import ActiveAppMonitor, match_excluded_app
from backend.core.steadyhand.filter import ClickBounceGuard, ScrollJitterFilter
from backend.core.steadyhand.gravity_wells import AccessibilityGravityWells, GravityTarget
from backend.core.steadyhand.metrics import MotorTelemetry
from backend.core.steadyhand.worker import SteadyHandWorker
from backend.db.database import Database


def test_delta_space_os_tap_preserves_full_sweep_distance_and_dampens_tremor():
    worker = SteadyHandWorker(tick_hz=60.0)
    worker.configure(enabled=True, strength=1.0, min_cutoff=0.6, beta=0.004, gravity_wells=False)
    worker._interceptor._mode = "quartz_cgeventtap"
    worker._system_mouse_enabled = True

    # Simulate a 300px linear sweep where each OS cursor event arrives relative to prior emitted output.
    last_out = (100.0, 200.0)
    emitted = []
    for i in range(90):
        t = 1.0 + i / 60.0
        raw_delta_x = 5.0 if i > 0 and i <= 60 else 0.0
        tremor_delta = (
            6.0 * math.sin(2.0 * math.pi * 5.5 * t)
            - 6.0 * math.sin(2.0 * math.pi * 5.5 * (t - 1.0 / 60.0))
            if i > 0
            else 0.0
        )
        os_in_x = last_out[0] + raw_delta_x + tremor_delta
        os_in_y = last_out[1]
        worker._interceptor._set_event_info(
            {"button": "left", "dx": raw_delta_x, "dy": 0.0, "has_delta": False, "scroll_dy": 0.0, "modifiers": set()}
        )
        out = worker._on_tap_event("move", os_in_x, os_in_y, t)
        assert isinstance(out, tuple)
        last_out = out
        emitted.append(out[0])

    # Physical travel was 100 -> 400 (300px). Delta-space tracking converges near 400 without shrinkage.
    assert abs(emitted[-1] - 400.0) < 12.0


def test_hold_to_bypass_and_precision_slow_mode():
    worker = SteadyHandWorker()
    worker.configure(
        enabled=True,
        strength=1.4,
        gravity_wells=False,
        bypass_key="alt",
        precision_key="shift",
    )
    worker._interceptor._mode = "quartz_cgeventtap"

    # Hold-to-bypass returns None so raw OS event passes untouched
    worker._interceptor._set_event_info({"button": "left", "modifiers": {"alt"}})
    assert worker._on_tap_event("move", 250.0, 250.0, 1.0) is None
    assert worker.snapshot()["bypass_active"] is True

    # Release bypass, establish baseline at (250, 250)
    worker._interceptor._set_event_info({"button": "left", "modifiers": set()})
    worker._on_tap_event("move", 250.0, 250.0, 1.02)

    # Precision slow-mode scales +100px raw displacement down to ~35px
    worker._interceptor._set_event_info({"button": "left", "modifiers": {"shift"}})
    out = worker._on_tap_event("move", 350.0, 250.0, 1.04)
    assert isinstance(out, tuple)
    assert worker.snapshot()["precision_active"] is True
    assert worker._virtual_raw_pos is not None
    assert math.isclose(worker._virtual_raw_pos[0], 285.0, abs_tol=1.0)


def test_bounce_guard_scroll_filter_and_real_slip_click_rescue():
    metrics = MotorTelemetry()
    bounce = ClickBounceGuard(metrics, click_debounce_ms=80, right_click_guard=True)
    scroll = ScrollJitterFilter(metrics, enabled=True, reversal_window_ms=120)

    assert bounce.allow_down("left", 1.000) is True
    assert bounce.allow_up("left", 1.050) is True
    # Accidental bounce 30ms later (< 80ms) is suppressed along with its matching release
    assert bounce.allow_down("left", 1.080) is False
    assert bounce.allow_up("left", 1.095) is False
    assert metrics.double_clicks_blocked == 1

    # Accidental right-click twitch 40ms after a left release is blocked
    assert bounce.allow_down("right", 1.090) is False
    assert bounce.allow_up("right", 1.110) is False

    # Legitimate click after cooldown passes cleanly
    assert bounce.allow_down("left", 1.300) is True

    # Scroll jitter reversal within 120ms is suppressed
    assert scroll.should_suppress(3.0, 2.00) is False
    assert scroll.should_suppress(-2.0, 2.05) is True
    assert scroll.should_suppress(-2.0, 2.25) is False
    assert metrics.scroll_jitters_filtered == 1

    # Worker tracks real slip_clicks_rescued when pointer slips past drag_threshold_px during click
    worker = SteadyHandWorker()
    worker.configure(enabled=True, anti_drag=True, anti_drag_threshold_px=6.0, click_freeze_ms=180)
    worker.process_sample(300.0, 300.0, timestamp=5.0, pressed=True)
    worker.process_sample(312.0, 304.0, timestamp=5.06)
    snap = worker.process_sample(310.0, 302.0, timestamp=5.12, pressed=False)
    assert snap["slip_clicks_rescued"] == 1


def test_async_gravity_wells_never_blocks_hook_and_uses_cached_targets(monkeypatch):
    wells = AccessibilityGravityWells(enabled=True, expansion=2.6, strength=0.5, velocity_threshold_px_s=500.0)
    target = GravityTarget(role="AXButton", x=100.0, y=100.0, width=40.0, height=20.0, title="OK")

    def slow_probe(_x: float, _y: float):
        time.sleep(0.05)
        return [target]

    monkeypatch.setattr(wells, "_probe_once", slow_probe)
    try:
        t0 = time.perf_counter()
        # First call schedules background probe and returns immediately in <10ms
        out = wells.apply_pull(140.0, 110.0, 1.0)
        elapsed = time.perf_counter() - t0
        assert out == (140.0, 110.0)
        assert elapsed < 0.02

        # Once background thread finishes probing, apply_pull magnetically pulls toward target center (120, 110)
        time.sleep(0.1)
        pulled_x, _ = wells.apply_pull(139.0, 110.0, 1.05)
        assert pulled_x < 139.0
    finally:
        wells.stop_prober()


def test_multiband_welch_psd_separates_resting_and_essential_tremor_with_pause_resilience():
    telemetry = MotorTelemetry(max_history=25)
    # 5.0 Hz resting tremor with a 0.35s thinking pause at t=1.5s..1.85s (must NOT wipe window!)
    for i in range(210):
        t = i / 60.0
        if 1.50 < t < 1.85:
            continue
        x = 500.0 + 18.0 * math.sin(2.0 * math.pi * 5.0 * t)
        y = 300.0 + 0.8 * i
        telemetry.sample(x, y, t, simulated=False, dpi_scale=1.0, filtered_pos=(500.0, y))

    assert telemetry.latest is not None
    assert telemetry.latest["resting_band_pct"] > telemetry.latest["action_band_pct"]
    assert telemetry.latest["rms_amplitude_px"] > 5.0
    assert telemetry.latest["rms_amplitude_mm"] > 1.0
    assert 4.0 <= telemetry.latest["dominant_hz"] <= 6.2

    # 8.5 Hz essential / action tremor concentrates in 6-12 Hz action band
    et_telemetry = MotorTelemetry(max_history=5)
    for i in range(210):
        t = i / 60.0
        x = 500.0 + 15.0 * math.sin(2.0 * math.pi * 8.5 * t)
        et_telemetry.sample(x, 300.0, t, simulated=False)
    assert et_telemetry.latest is not None
    assert et_telemetry.latest["action_band_pct"] > et_telemetry.latest["resting_band_pct"]
    assert 6.5 <= et_telemetry.latest["dominant_hz"] <= 10.5

    # Bounded history deque cap
    for k in range(30):
        et_telemetry.sample(500.0 + (k % 10) * 15.0, 300.0, 5.0 + k * 0.6, simulated=False)
    assert len(et_telemetry.history) <= 5


def test_per_app_exclusions_bypass_stabilization():
    assert match_excluded_app("Figma (com.figma.Desktop)", ["Photoshop", "figma"]) == "figma"
    assert match_excluded_app("Safari", ["Photoshop", "figma"]) is None

    worker = SteadyHandWorker()
    worker.configure(enabled=True, excluded_apps=["Figma"])
    worker.app_monitor.stop()
    worker.app_monitor.update_active_app("Figma")
    worker._interceptor._mode = "quartz_cgeventtap"
    worker._interceptor._set_event_info({"button": "left", "modifiers": set()})

    assert worker._on_tap_event("move", 420.0, 310.0, 2.0) is None
    assert worker.snapshot()["excluded_app_active"] == "Figma"
    worker.app_monitor.stop()


def test_background_persistence_clinical_events_and_simulation_filtering(tmp_path):
    db_path = tmp_path / "clinical.db"
    db = Database(db_path)
    coord = EngineCoordinator(db=db, auto_start_workers=False)

    # Feed real (non-simulated) samples directly to steady_worker WITHOUT opening any WebSocket
    coord.steady_worker.configure(enabled=True, simulate_tremor=False)
    for i in range(210):
        t = 10.0 + i / 60.0
        coord.steady_worker.process_sample(
            400.0 + 14.0 * math.sin(2.0 * math.pi * 5.2 * t),
            300.0,
            timestamp=t,
        )

    real_rows = db.get_tremor_history(limit=20, include_simulated=False)
    assert len(real_rows) >= 1

    # Add a simulated row and confirm default clinician query excludes it
    db.record_tremor_sample(
        session_id="demo-sim",
        timestamp=time.time(),
        sample_time=99.0,
        tremor_index=85.0,
        dominant_hz=5.5,
        stability_score=20.0,
        medication_state_estimate="OFF",
        stabilization_active=True,
        simulated=True,
    )

    app = create_app(coordinator=coord, db_path=db_path, auto_start_workers=False)
    with TestClient(app) as client:
        default_sess = client.get("/api/sessions?days=14").json()
        assert all(s["session_id"] != "demo-sim" for s in default_sess["sessions"])
        assert default_sess["simulated_sample_count"] == 1
        assert len(default_sess["hourly_profile"]) >= 1
        assert default_sess["functional_summary"]["total_samples"] >= 1

        with_sim = client.get("/api/sessions?days=14&include_simulated=true").json()
        assert any(s["session_id"] == "demo-sim" for s in with_sim["sessions"])

        # Clinical Event Diary CRUD
        ev = client.post(
            "/api/events",
            json={
                "event_type": "medication",
                "label": "Sinemet 25/100",
                "dosage": "1 tablet",
                "severity": 2,
                "notes": "Morning dose",
            },
        )
        assert ev.status_code == 200
        ev_id = ev.json()["id"]

        listed = client.get("/api/events?days=7").json()["events"]
        assert len(listed) == 1
        assert listed[0]["label"] == "Sinemet 25/100"

        deleted = client.delete(f"/api/events/{ev_id}")
        assert deleted.status_code == 200
        assert client.get("/api/events?days=7").json()["events"] == []

    coord.shutdown()


def test_local_api_token_auth_and_sandbox_isolation(tmp_path):
    token = "secret-local-token-1234"
    app = create_app(db_path=tmp_path / "auth.db", auto_start_workers=False, api_token=token)
    with TestClient(app) as client:
        # Health stays accessible for sidecar readiness check
        assert client.get("/api/health").status_code == 200

        # Protected endpoints reject missing/bad token
        assert client.get("/api/settings").status_code == 401
        assert client.get("/api/settings", headers={"X-ClearCursor-Token": "wrong"}).status_code == 401
        assert client.get("/api/settings", headers={"X-ClearCursor-Token": token}).status_code == 200

        # WebSocket rejects unauthorized and accepts valid token query
        with pytest.raises(Exception):
            with client.websocket_connect("/ws/telemetry?hz=25"):
                pass
        with client.websocket_connect(f"/ws/telemetry?hz=25&token={token}") as ws:
            msg = ws.receive_json()
            assert "stability_score" in msg

        # Sandbox sample isolation: must NOT pollute steady_worker or SQLite tremor_history
        coord = app.state.coordinator
        coord.steady_worker.controller.last_raw = (999.0, 999.0)
        for i in range(180):
            res = client.post(
                "/api/steadyhand/sample",
                headers={"X-ClearCursor-Token": token},
                json={"x": 120.0 + i, "y": 150.0, "timestamp": 1.0 + i / 60.0, "sandbox": True},
            )
            assert res.status_code == 200

        assert coord.steady_worker.controller.last_raw == (999.0, 999.0)
        assert coord.db.get_tremor_history(limit=50) == []


def test_ws_disconnect_preserves_steadyhand_while_stopping_gaze(tmp_path):
    db = Database(tmp_path / "tray.db")
    coord = EngineCoordinator(db=db, auto_start_workers=False)
    try:
        coord.update_settings({"steady_hand": True, "gaze_control": True, "system_mouse": True})
        res = coord.stop_gaze_on_disconnect()
        assert res["camera_running"] is False
        assert res["settings"]["gaze_control"] is False
        assert res["settings"]["steady_hand"] is True
        assert res["settings"]["system_mouse"] is True
    finally:
        coord.shutdown()
