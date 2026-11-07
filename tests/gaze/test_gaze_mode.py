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
    assert "3 gaze selections" in messages[-1]
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
    assert messages and messages[0].startswith("Gaze: ")
