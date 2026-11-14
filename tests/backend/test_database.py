from backend.core.engine.settings import AccessibilitySettings
from backend.core.gaze.calibration import GazeCalibration
from backend.db.database import Database


def test_settings_round_trip(tmp_path):
    db = Database(tmp_path / "test.db")
    try:
        defaults = db.load_settings()
        assert defaults.profile == "parkinsons"
        assert defaults.gaze_dwell_ms == 1100

        updated = AccessibilitySettings(
            profile="als",
            gaze_control=True,
            steady_hand=False,
            tremor_strength=145,
            gaze_dwell_ms=850,
            blink_select=False,
        )
        db.save_settings(updated)
        reloaded = db.load_settings()
        assert reloaded.profile == "als"
        assert reloaded.gaze_control is True
        assert reloaded.steady_hand is False
        assert reloaded.tremor_strength == 145
        assert reloaded.gaze_dwell_ms == 850
        assert reloaded.blink_select is False
    finally:
        db.close()


def test_calibration_profile_activation_and_restore(tmp_path):
    db = Database(tmp_path / "test.db")
    try:
        feats = [(0.3, -0.1), (0.5, 0.0), (0.7, 0.1), (0.3, 0.1)]
        targets = [(1000 * u + 20, 1500 * v + 400) for u, v in feats]
        cal = GazeCalibration()
        cal.fit(feats, targets)
        err = cal.error_px(feats, targets)

        first_id = db.save_calibration_profile(
            name="first",
            source="eyes",
            calibration_dict=cal.to_dict(),
            error_px=err,
            open_ears=[0.31, 0.32],
        )
        second_id = db.save_calibration_profile(
            name="second",
            source="eyes",
            calibration_dict=cal.to_dict(),
            error_px=12.5,
            open_ears=[0.29, 0.30],
        )
        assert second_id > first_id

        active = db.get_active_calibration("eyes")
        assert active is not None
        assert active["id"] == second_id
        assert active["error_px"] == 12.5
        restored = GazeCalibration.from_dict(active["calibration"])
        assert restored.map((0.5, 0.0)) == cal.map((0.5, 0.0))
        assert len(db.list_calibration_profiles()) == 2
    finally:
        db.close()


def test_tremor_history_persistence(tmp_path):
    db = Database(tmp_path / "test.db")
    try:
        db.record_tremor_sample(
            session_id="sess-1",
            timestamp=1000.0,
            sample_time=4.0,
            tremor_index=62.5,
            dominant_hz=5.5,
            stability_score=42.0,
            medication_state_estimate="OFF",
            stabilization_active=True,
            simulated=True,
        )
        db.record_tremor_sample(
            session_id="sess-2",
            timestamp=1001.0,
            sample_time=4.5,
            tremor_index=12.0,
            dominant_hz=None,
            stability_score=88.0,
            medication_state_estimate="ON",
            stabilization_active=True,
            simulated=False,
        )
        all_rows = db.get_tremor_history(limit=10)
        assert len(all_rows) == 2
        sess1_rows = db.get_tremor_history(limit=10, session_id="sess-1")
        assert len(sess1_rows) == 1
        assert sess1_rows[0]["dominant_hz"] == 5.5
        assert sess1_rows[0]["medication_state_estimate"] == "OFF"
    finally:
        db.close()
