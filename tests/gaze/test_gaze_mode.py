import time

from PySide6.QtCore import QCoreApplication, QRect
from PySide6.QtWidgets import QPushButton

from accessshift.ui.gaze_mode import GazeMode


class FakeTracker:
    def __init__(self):
        self.closed = False

    def open(self):
        return True

    def read(self):
        time.sleep(0.005)
        return {"camera_ok": True, "face": False, "ts_ms": int(time.monotonic() * 1000)}

    def close(self):
        self.closed = True


def make_mode():
    return GazeMode(
        screen_rect=QRect(0, 0, 1000, 800),
        tracker_factory=FakeTracker,
        calibrate_on_start=False,
    )


def test_enable_starts_camera_and_overlay_disable_stops(qapp):
    gm = make_mode()
    gm.set_enabled(True)
    assert gm.controller.running and gm.overlay.isVisible()
    gm.set_enabled(True)  # idempotent
    gm.set_enabled(False)
    assert not gm.controller.running and not gm.overlay.isVisible()
    gm.set_enabled(False)  # idempotent


def test_booking_reports_selections_and_time(qapp):
    gm = make_mode()
    messages = []
    gm.status.connect(messages.append)
    gm.metrics.start_task(0)
    gm.controller.selected.emit(QPushButton("Myself"))
    gm.controller.selected.emit(QPushButton("Check-up"))
    gm.controller.selected.emit(QPushButton("Book appointment"))
    assert "3 selections" in messages[-1]
    assert gm.metrics.summary()["selections"] == 3 and gm.metrics.summary()["task_ms"] is not None


def test_controller_status_is_forwarded(qapp):
    gm = make_mode()
    messages = []
    gm.status.connect(messages.append)
    gm.set_enabled(True)
    end = time.monotonic() + 3
    while not messages and time.monotonic() < end:
        QCoreApplication.processEvents()
        time.sleep(0.01)
    gm.set_enabled(False)
    assert messages and messages[0] == "Calibrate first"  # forwarded as-is, no "Gaze:" prefix


def test_recalibrate_uses_head_steps_and_switching_to_eyes_asks_for_eye_calibration(qapp, monkeypatch):
    from accessshift.ui import gaze_calibration_dialog as dialog_mod

    runs = []

    def fake_run(self):
        runs.append(len(self._points))  # 5 head poses or 9 eye dots
        return False

    monkeypatch.setattr(dialog_mod.GazeCalibrationDialog, "run", fake_run)
    gm = GazeMode(screen_rect=QRect(0, 0, 1000, 800), tracker_factory=FakeTracker, calibrate_on_start=True)
    gm.set_enabled(True)
    gm.recalibrate()
    gm.toggle_source()  # -> eyes: should prompt eye calibration
    end = time.monotonic() + 2
    while len(runs) < 3 and time.monotonic() < end:  # first run is the automatic one on enable
        QCoreApplication.processEvents()
        time.sleep(0.01)
    gm.set_enabled(False)
    assert gm.controller.source == "eyes"
    assert 5 in runs and runs[-1] == 9  # head recalibration, then eye calibration after the switch


def test_calibration_never_opens_twice_at_once(qapp, monkeypatch):
    from accessshift.ui import gaze_calibration_dialog as dialog_mod

    gm = GazeMode(screen_rect=QRect(0, 0, 1000, 800), tracker_factory=FakeTracker, calibrate_on_start=False)
    runs = []

    def fake_run(self):
        runs.append(1)
        gm.recalibrate()  # e.g. the automatic calibration firing while this one is open
        return False

    monkeypatch.setattr(dialog_mod.GazeCalibrationDialog, "run", fake_run)
    gm.set_enabled(True)
    gm.recalibrate()
    gm.set_enabled(False)
    assert runs == [1]


def test_cancelled_calibration_reports_a_problem(qapp, monkeypatch):
    from accessshift.ui import gaze_calibration_dialog as dialog_mod

    monkeypatch.setattr(dialog_mod.GazeCalibrationDialog, "run", lambda self: False)  # Esc
    gm = GazeMode(screen_rect=QRect(0, 0, 1000, 800), tracker_factory=FakeTracker, calibrate_on_start=False)
    problems = []
    gm.problem.connect(problems.append)
    gm.set_enabled(True)
    gm.recalibrate()
    gm.set_enabled(False)
    assert problems and "cancelled" in problems[0].lower() and "—" not in problems[0]


def test_camera_failure_reports_a_problem(qapp):
    gm = GazeMode(screen_rect=QRect(0, 0, 1000, 800), calibrate_on_start=False)
    problems = []
    gm.problem.connect(problems.append)
    gm.controller.status.emit("Camera could not be opened. On macOS allow camera access.")
    assert problems and problems[0].startswith("Camera")
