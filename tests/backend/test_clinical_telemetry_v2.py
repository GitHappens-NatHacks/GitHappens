"""Tests for honest diurnal coverage, 15-second motor check-ins, and opt-in keyboard timing telemetry."""

from __future__ import annotations

import math
import time

from fastapi.testclient import TestClient

from backend.api.main import create_app
from backend.core.engine.coordinator import EngineCoordinator
from backend.core.steadyhand.checkin import evaluate_motor_checkin
from backend.core.steadyhand.keyboard_cadence import KeyboardCadenceMonitor
from backend.db.database import Database


def test_diurnal_hourly_grid_and_honest_coverage_summary(tmp_path):
    db = Database(tmp_path / "coverage.db")
    now = time.time()
    # Record two distinct minutes in the current hour and leave all other 23 hours empty
    db.record_tremor_sample(
        session_id="sess-1",
        timestamp=now - 120.0,
        sample_time=10.0,
        tremor_index=22.0,
        dominant_hz=5.1,
        stability_score=78.0,
        medication_state_estimate="ON",
        stabilization_active=True,
        simulated=False,
    )
    db.record_tremor_sample(
        session_id="sess-1",
        timestamp=now,
        sample_time=70.0,
        tremor_index=26.0,
        dominant_hz=5.3,
        stability_score=74.0,
        medication_state_estimate="ON",
        stabilization_active=True,
        simulated=False,
    )

    summary = db.get_session_summaries(days=7, include_simulated=False)
    grid = summary["hourly_grid"]
    assert len(grid) == 24
    observed = [h for h in grid if h["has_data"]]
    empty = [h for h in grid if not h["has_data"]]
    assert len(observed) >= 1
    assert len(empty) >= 22
    # Empty hours must explicitly remain None rather than fake 0 stability
    assert all(h["avg_stability_score"] is None and h["active_minutes"] == 0 for h in empty)
    assert sum(h["active_minutes"] for h in observed) == 2

    cov = summary["coverage_summary"]
    assert cov["telemetry_scope"] == "functional_computer_use"
    assert cov["total_active_minutes"] == 2
    assert cov["active_days"] == 1
    assert cov["window_days"] == 7
    db.close()


def test_motor_checkin_scoring_and_api_crud(tmp_path):
    # Steady hold vs 5 Hz tremor hold
    steady_samples = [
        {"x": 200.0 + 0.5 * math.sin(i * 0.2), "y": 200.0, "t": i / 60.0}
        for i in range(200)
    ]
    tremor_samples = [
        {"x": 200.0 + 18.0 * math.sin(2.0 * math.pi * 5.2 * (i / 60.0)), "y": 200.0, "t": i / 60.0}
        for i in range(200)
    ]

    steady_res = evaluate_motor_checkin(
        hold_samples=steady_samples,
        target_x=200.0,
        target_y=200.0,
        taps=[
            {"target_x": 100.0, "target_y": 100.0, "click_x": 103.0, "click_y": 98.0, "reaction_ms": 420.0},
            {"target_x": 300.0, "target_y": 150.0, "click_x": 297.0, "click_y": 152.0, "reaction_ms": 380.0},
        ],
        context_tag="post_medication",
        notes="45 min after morning dose",
    )
    tremor_res = evaluate_motor_checkin(
        hold_samples=tremor_samples,
        target_x=200.0,
        target_y=200.0,
        taps=[
            {"target_x": 100.0, "target_y": 100.0, "click_x": 140.0, "click_y": 125.0, "reaction_ms": 950.0},
        ],
        context_tag="pre_medication",
    )

    assert steady_res["hold_stability_score"] > tremor_res["hold_stability_score"] + 15.0
    assert steady_res["overall_score"] > tremor_res["overall_score"] + 20.0
    assert steady_res["tap_accuracy_pct"] == 100.0
    assert tremor_res["tap_accuracy_pct"] == 0.0
    assert tremor_res["hold_dominant_hz"] is not None
    assert 4.0 <= tremor_res["hold_dominant_hz"] <= 6.5

    # REST API round-trip + inclusion in /api/sessions
    app = create_app(db_path=tmp_path / "checkins.db", auto_start_workers=False)
    with TestClient(app) as client:
        created = client.post(
            "/api/checkins",
            json={
                "hold_samples": steady_samples,
                "target_x": 200.0,
                "target_y": 200.0,
                "taps": [
                    {"target_x": 100.0, "target_y": 100.0, "click_x": 102.0, "click_y": 101.0, "reaction_ms": 410.0}
                ],
                "context_tag": "post_medication",
                "notes": "Morning check",
            },
        )
        assert created.status_code == 200
        body = created.json()
        cid = body["id"]
        assert body["context_tag"] == "post_medication"
        assert body["tap_accuracy_pct"] == 100.0

        listed = client.get("/api/checkins?days=14").json()["checkins"]
        assert len(listed) == 1
        assert listed[0]["id"] == cid

        sessions = client.get("/api/sessions?days=14").json()
        assert len(sessions["motor_checkins"]) == 1
        assert sessions["coverage_summary"]["checkin_count"] == 1

        deleted = client.delete(f"/api/checkins/{cid}")
        assert deleted.status_code == 200
        assert client.get("/api/checkins?days=14").json()["checkins"] == []


def test_keyboard_cadence_privacy_and_persistence(tmp_path):
    # Disabled by default; ignores timing events until explicitly enabled
    windows: list[dict] = []
    mon = KeyboardCadenceMonitor(window_size=10, on_window_ready=windows.append)
    assert mon.enabled is False
    assert mon.record_timing_event("down", 1, 1.0) is None
    assert mon.record_timing_event("up", 1, 1.09) is None
    assert mon.snapshot()["total_keystrokes"] == 0

    mon.set_enabled(True, attach_os_listener=False)
    t = 10.0
    for idx in range(10):
        mon.record_timing_event("down", idx, t)
        # 85ms hold duration, 110ms flight time
        mon.record_timing_event("up", idx, t + 0.085)
        t += 0.195

    assert len(windows) == 1
    win = windows[0]
    assert win["sample_count"] == 10
    assert 80.0 <= win["mean_hold_ms"] <= 90.0
    assert 105.0 <= win["mean_flight_ms"] <= 115.0
    assert win["rhythm_regularity_score"] >= 85.0
    # Strict privacy check: no key names or characters stored anywhere in output
    assert set(win.keys()) == {
        "timestamp",
        "sample_count",
        "mean_hold_ms",
        "std_hold_ms",
        "mean_flight_ms",
        "std_flight_ms",
        "typing_cadence_kpm",
        "rhythm_regularity_score",
    }

    # Coordinator + SQLite + /api/cadence integration
    db = Database(tmp_path / "cadence.db")
    coord = EngineCoordinator(db=db, auto_start_workers=False)
    try:
        assert coord.settings.keyboard_cadence_telemetry is False
        coord.keyboard_monitor.set_enabled(True, attach_os_listener=False)
        t = 50.0
        for idx in range(6):
            coord.keyboard_monitor.record_timing_event("down", idx, t)
            coord.keyboard_monitor.record_timing_event("up", idx, t + 0.14)
            t += 0.30
        flushed = coord.keyboard_monitor.flush()
        assert flushed is not None

        app = create_app(coordinator=coord, db_path=tmp_path / "cadence.db", auto_start_workers=False)
        with TestClient(app) as client:
            res = client.get("/api/cadence?days=14").json()
            assert res["summary"]["window_count"] == 1
            assert res["summary"]["total_keystrokes"] == 6
            assert 135.0 <= res["summary"]["avg_hold_ms"] <= 145.0

            sess = client.get("/api/sessions?days=14").json()
            assert sess["keyboard_cadence_summary"]["window_count"] == 1
            assert sess["coverage_summary"]["keyboard_cadence_windows"] == 1
    finally:
        coord.shutdown()
