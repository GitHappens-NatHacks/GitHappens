"""Phase 5 robustness, edge-case, concurrency, and OS-hook tests."""

from __future__ import annotations

import builtins
import sqlite3
import sys
import threading
import types
from types import SimpleNamespace

from fastapi.testclient import TestClient

from backend.api.main import create_app
from backend.core.steadyhand.filter import IntentionalHold
from backend.core.steadyhand.gravity_wells import AccessibilityGravityWells, GravityTarget
from backend.core.steadyhand.metrics import MotorTelemetry
from backend.core.steadyhand.os_tap import SystemCursorInterceptor
from backend.core.steadyhand.worker import SteadyHandWorker
from backend.db.database import Database


def test_api_query_bounds_and_calibration_errors(tmp_path):
    app = create_app(db_path=tmp_path / "bounds.db", auto_start_workers=False)
    with TestClient(app) as client:
        assert client.get("/api/history?limit=0").status_code == 422
        assert client.get("/api/history?limit=5000").status_code == 422
        assert client.get("/api/sessions?days=0").status_code == 422
        assert client.get("/api/sessions?days=999").status_code == 422
        assert client.get("/api/sessions?limit=999").status_code == 422

        bad_cal = client.post("/api/calibrate", json={"mode": "head", "source": "head"})
        assert bad_cal.status_code == 400

        bad_dots = client.post(
            "/api/calibrate",
            json={
                "mode": "dots",
                "source": "eyes",
                "features": [[0.1, 0.1]],
                "targets": [[100.0, 100.0], [200.0, 200.0]],
            },
        )
        assert bad_dots.status_code == 400


def test_concurrent_websockets_and_medication_presets(tmp_path):
    app = create_app(db_path=tmp_path / "ws_multi.db", auto_start_workers=True)
    with TestClient(app) as client:
        for preset in ("mild", "moderate", "high", "hands_free"):
            res = client.post("/api/settings", json={"profile": preset})
            assert res.status_code == 200
            assert res.json()["profile"] == preset

        with client.websocket_connect("/ws/telemetry?hz=25") as ws1:
            with client.websocket_connect("/ws/telemetry?hz=25") as ws2:
                msg1 = ws1.receive_json()
                msg2 = ws2.receive_json()
                assert msg1["session_id"] == msg2["session_id"]
                assert "click_freeze_active" in msg1["steadyhand"]
                assert "gravity_well_active" in msg1["steadyhand"]
                assert "os_tap_mode" in msg1["steadyhand"]


def test_database_recovers_corrupt_settings_and_handles_concurrent_writes(tmp_path):
    db_path = tmp_path / "corrupt.db"
    db = Database(db_path)

    # Inject malformed JSON directly into settings row
    with sqlite3.connect(str(db_path)) as conn:
        conn.execute(
            "INSERT OR REPLACE INTO settings (id, payload_json, updated_at) VALUES (1, ?, 1.0)",
            ("{not-valid-json",),
        )
        conn.commit()

    recovered = db.load_settings()
    assert recovered.click_freeze_ms == 180
    assert recovered.gravity_wells is True

    # Threaded concurrent tremor writes must remain consistent under RLock + WAL
    errors: list[Exception] = []

    def writer(worker_idx: int) -> None:
        try:
            for sample_idx in range(10):
                db.record_tremor_sample(
                    session_id=f"sess-{worker_idx}",
                    timestamp=1700000000.0 + sample_idx,
                    sample_time=float(sample_idx),
                    tremor_index=25.0 + worker_idx,
                    dominant_hz=5.2,
                    stability_score=85.0,
                    medication_state_estimate="ON",
                    stabilization_active=True,
                    simulated=True,
                )
        except Exception as exc:  # pragma: no cover
            errors.append(exc)

    threads = [threading.Thread(target=writer, args=(i,)) for i in range(4)]
    for th in threads:
        th.start()
    for th in threads:
        th.join()

    assert errors == []
    summary = db.get_session_summaries(days=14, limit=20)
    assert len(summary["sessions"]) == 4
    db.close()


def test_quartz_tap_lifecycle_rewrites_events_and_cleans_up_port(monkeypatch):
    calls: dict[str, object] = {
        "enabled": [],
        "invalidated": False,
        "stopped": False,
        "set_locations": [],
        "callback": None,
    }
    fake_tap = object()
    fake_loop = object()

    class _FakeQuartz:
        kCGEventMouseMoved = 5
        kCGEventLeftMouseDragged = 6
        kCGEventLeftMouseDown = 1
        kCGEventLeftMouseUp = 2
        kCGEventTapDisabledByTimeout = 0xFFFFFFFE
        kCGEventTapDisabledByUserInput = 0xFFFFFFFF
        kCGHIDEventTap = 0
        kCGHeadInsertEventTap = 0
        kCGEventTapOptionDefault = 0
        kCFRunLoopCommonModes = "common"

        @staticmethod
        def CGEventGetLocation(event):
            return SimpleNamespace(x=event["x"], y=event["y"])

        @staticmethod
        def CGPoint(x, y):
            return (x, y)

        @staticmethod
        def CGEventSetLocation(_event, pt):
            calls["set_locations"].append(pt)

        @staticmethod
        def CGEventTapCreate(_tap, _place, _opts, _mask, cb, _ref):
            calls["callback"] = cb
            return fake_tap

        @staticmethod
        def CFMachPortCreateRunLoopSource(_alloc, _tap, _order):
            return object()

        @staticmethod
        def CFRunLoopGetCurrent():
            return fake_loop

        @staticmethod
        def CFRunLoopAddSource(_loop, _source, _mode):
            return None

        @staticmethod
        def CGEventTapEnable(_tap, state):
            calls["enabled"].append(state)

        @staticmethod
        def CFMachPortInvalidate(_tap):
            calls["invalidated"] = True

        @staticmethod
        def CFRunLoopRun():
            return None

        @staticmethod
        def CFRunLoopStop(_loop):
            calls["stopped"] = True

    class _FakeAS:
        @staticmethod
        def AXIsProcessTrusted():
            return True

    monkeypatch.setattr(sys, "platform", "darwin")
    monkeypatch.setitem(sys.modules, "Quartz", _FakeQuartz)
    monkeypatch.setitem(sys.modules, "ApplicationServices", _FakeAS)

    seen_events: list[tuple[str, float, float]] = []

    def handler(kind: str, x: float, y: float, _now: float):
        seen_events.append((kind, x, y))
        if kind == "move" and x < 0:
            raise RuntimeError("boom inside callback")
        return (x - 5.0, y + 3.0)

    interceptor = SystemCursorInterceptor(handler)
    ok, err = interceptor.start()
    assert ok is True
    assert err is None
    assert interceptor.mode == "quartz_cgeventtap"

    cb = calls["callback"]
    assert callable(cb)

    # Normal move event rewrites coordinates in-place
    ev = {"x": 200.0, "y": 300.0}
    cb(None, _FakeQuartz.kCGEventMouseMoved, ev, None)
    assert seen_events[-1] == ("move", 200.0, 300.0)
    assert calls["set_locations"][-1] == (195.0, 303.0)

    # Timeout re-enables the tap automatically
    cb(None, _FakeQuartz.kCGEventTapDisabledByTimeout, ev, None)
    assert calls["enabled"][-1] is True

    # Callback exception does not propagate out of Quartz C callback
    bad_ev = {"x": -10.0, "y": 50.0}
    assert cb(None, _FakeQuartz.kCGEventMouseMoved, bad_ev, None) is bad_ev

    interceptor.stop()
    assert False in calls["enabled"]
    assert calls["invalidated"] is True
    assert calls["stopped"] is True
    assert interceptor.mode == "idle"


def test_interceptor_falls_back_when_ax_untrusted_and_pynput_missing(monkeypatch):
    class _UntrustedAS:
        @staticmethod
        def AXIsProcessTrusted():
            return False

    monkeypatch.setattr(sys, "platform", "darwin")
    monkeypatch.setitem(sys.modules, "Quartz", types.SimpleNamespace())
    monkeypatch.setitem(sys.modules, "ApplicationServices", _UntrustedAS)

    real_import = builtins.__import__

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "pynput" or name.startswith("pynput."):
            raise ImportError("pynput unavailable")
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    interceptor = SystemCursorInterceptor(lambda *_a: None)
    ok, err = interceptor.start()
    assert ok is False
    assert interceptor.mode == "idle"
    assert err is not None


def test_gravity_wells_disables_cleanly_and_picks_nearest_well():
    wells = AccessibilityGravityWells(enabled=True, expansion=2.6, strength=0.5, velocity_threshold_px_s=500.0)
    left_btn = GravityTarget(role="AXButton", x=100.0, y=100.0, width=40.0, height=24.0, title="Cancel")
    right_btn = GravityTarget(role="AXCloseButton", x=170.0, y=100.0, width=40.0, height=24.0, title="Confirm")

    # Prime velocity history near right button center (190, 112)
    wells.apply_pull(186.0, 112.0, 1.0, targets=[left_btn, right_btn])
    px, _ = wells.apply_pull(185.0, 112.0, 1.05, targets=[left_btn, right_btn])
    assert px > 185.0
    assert wells.snapshot()["gravity_target_role"] == "AXCloseButton"

    # Disabling immediately clears active lock state
    wells.configure(enabled=False)
    assert wells.apply_pull(185.0, 112.0, 1.1, targets=[left_btn, right_btn]) == (185.0, 112.0)
    assert wells.snapshot()["gravity_well_active"] is False


def test_click_freeze_releases_early_on_25px_intentional_drag():
    metrics = MotorTelemetry()
    hold = IntentionalHold(metrics)
    hold.configure(click_freeze_ms=180, drag_release_px=25.0, hold_seconds=0.1, latch_distance_px=25.0)

    # First press: < 25px travel past hold_seconds (140ms < 180ms click freeze) remains frozen
    hold.press((300.0, 300.0), (300.0, 300.0), 1.0)
    hold.move((306.0, 300.0), (306.0, 300.0), 1.04)
    hold.move((312.0, 300.0), (312.0, 300.0), 1.09)
    locked = hold.move((316.0, 300.0), (316.0, 300.0), 1.15)
    assert hold.click_freeze_active is True
    assert hold.dragging is False
    assert locked == (300.0, 300.0)
    hold.release((316.0, 300.0), slipped=False)

    # Second press: > 25px coherent travel before 180ms (150ms > hold_seconds=0.1) unlocks drag early
    hold.press((300.0, 300.0), (300.0, 300.0), 2.0)
    hold.move((308.0, 300.0), (308.0, 300.0), 2.04)
    hold.move((318.0, 300.0), (318.0, 300.0), 2.09)
    out = hold.move((330.0, 300.0), (330.0, 300.0), 2.15)
    assert hold.click_freeze_active is False
    assert hold.dragging is True
    assert out == (330.0, 300.0)


def test_steadyhand_worker_simulate_tremor_emits_welch_fft_window():
    worker = SteadyHandWorker(tick_hz=60.0)
    worker.configure(enabled=True, simulate_tremor=True, tremor_intensity=75, click_freeze_ms=180)
    for i in range(260):
        worker.process_sample(500.0, 400.0, timestamp=1.0 + i / 60.0)

    snap = worker.snapshot()
    assert snap["tremor_hz"] is not None
    assert 3.5 <= snap["tremor_hz"] <= 7.5
    assert snap["tremor_index"] > 0.0
    record = worker.consume_latest_fft_record()
    assert record is not None
    assert record["simulated"] is True
