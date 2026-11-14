from fastapi.testclient import TestClient

from backend.api.main import create_app


def test_rest_settings_calibration_toggle_and_history(tmp_path):
    db_path = tmp_path / "api_test.db"
    app = create_app(db_path=db_path, auto_start_workers=False)

    with TestClient(app) as client:
        health = client.get("/api/health")
        assert health.status_code == 200
        assert health.json()["status"] == "ok"

        # Settings GET and POST
        s0 = client.get("/api/settings")
        assert s0.status_code == 200
        assert s0.json()["profile"] == "parkinsons"

        s1 = client.post(
            "/api/settings",
            json={
                "tremor_strength": 150,
                "one_euro_min_cutoff": 0.45,
                "one_euro_beta": 0.008,
                "anti_drag_threshold_px": 12.0,
                "anti_drag_hold_ms": 450,
                "gaze_dwell_ms": 900,
                "blink_select": False,
            },
        )
        assert s1.status_code == 200
        body = s1.json()
        assert body["tremor_strength"] == 150
        assert body["one_euro_min_cutoff"] == 0.45
        assert body["one_euro_beta"] == 0.008
        assert body["anti_drag_threshold_px"] == 12.0
        assert body["anti_drag_hold_ms"] == 450
        assert body["gaze_dwell_ms"] == 900
        assert body["blink_select"] is False

        # Out-of-bounds validation
        bad = client.post("/api/settings", json={"tremor_strength": 999})
        assert bad.status_code == 422

        # Head calibration
        cal_head = client.post(
            "/api/calibrate",
            json={
                "mode": "head",
                "source": "head",
                "profile_name": "head-test",
                "poses": {
                    "center": [0.0, 0.2],
                    "left": [-0.2, 0.2],
                    "right": [0.2, 0.2],
                    "up": [0.0, 0.05],
                    "down": [0.0, 0.35],
                },
                "open_ears": [0.3, 0.32],
            },
        )
        assert cal_head.status_code == 200
        assert cal_head.json()["calibrated"] is True
        assert cal_head.json()["source"] == "head"

        # Dot calibration
        feats = [[0.3, -0.1], [0.5, 0.0], [0.7, 0.1], [0.3, 0.1]]
        targets = [[200.0, 150.0], [720.0, 450.0], [1240.0, 750.0], [200.0, 750.0]]
        cal_dots = client.post(
            "/api/calibrate",
            json={
                "mode": "dots",
                "source": "eyes",
                "profile_name": "eyes-test",
                "features": feats,
                "targets": targets,
            },
        )
        assert cal_dots.status_code == 200
        assert cal_dots.json()["calibrated"] is True

        # Engine toggle
        tog = client.post(
            "/api/engine/toggle",
            json={"steady_hand": True, "simulate_tremor": True, "gaze_control": True},
        )
        assert tog.status_code == 200
        assert tog.json()["settings"]["simulate_tremor"] is True
        assert tog.json()["settings"]["gaze_control"] is True

        # Feed 4+ seconds of simulated samples via REST and check DB history
        for i in range(260):
            resp = client.post(
                "/api/steadyhand/sample",
                json={"x": 500.0, "y": 400.0, "timestamp": i / 60.0},
            )
            assert resp.status_code == 200

        hist = client.get("/api/history")
        assert hist.status_code == 200
        hist_json = hist.json()
        assert len(hist_json["tremor_history"]) >= 1
        assert len(hist_json["calibration_profiles"]) == 2
        latest_row = hist_json["tremor_history"][0]
        assert 4.0 <= latest_row["dominant_hz"] <= 7.0

        sessions = client.get("/api/sessions")
        assert sessions.status_code == 200
        sess_json = sessions.json()
        assert len(sess_json["sessions"]) >= 1
        assert len(sess_json["daily_trends"]) >= 1
        assert sess_json["daily_trends"][0]["sample_count"] >= 1

    # Verify settings and calibration persist across app restarts.
    app2 = create_app(db_path=db_path, auto_start_workers=False)
    with TestClient(app2) as client2:
        s_reloaded = client2.get("/api/settings").json()
        assert s_reloaded["tremor_strength"] == 150
        assert s_reloaded["gaze_dwell_ms"] == 900
        assert client2.get("/api/health").json()["calibrated"] is True


def test_websocket_telemetry_stream(tmp_path):
    db_path = tmp_path / "ws_test.db"
    app = create_app(db_path=db_path, auto_start_workers=False)

    with TestClient(app) as client:
        client.post(
            "/api/engine/toggle",
            json={"steady_hand": True, "simulate_tremor": True},
        )
        for i in range(260):
            client.post(
                "/api/steadyhand/sample",
                json={"x": 300.0, "y": 250.0, "timestamp": i / 60.0},
            )

        with client.websocket_connect("/ws/telemetry?hz=25") as ws:
            frames = [ws.receive_json() for _ in range(3)]
            assert len(frames) == 3
            frame = frames[-1]
            assert frame["stabilization_active"] is True
            assert frame["tremor_hz"] is not None
            assert 4.0 <= frame["tremor_hz"] <= 7.0
            assert "stability_score" in frame
            assert "gaze" in frame and "x" in frame["gaze"] and "y" in frame["gaze"]
            assert "active_modes" in frame
