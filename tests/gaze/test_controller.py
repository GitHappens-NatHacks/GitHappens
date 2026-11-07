import time

import pytest
from PySide6.QtCore import QCoreApplication, QRect
from PySide6.QtWidgets import QLabel, QPushButton, QWidget

from accessshift.modules.gaze.calibration import GazeCalibration
from accessshift.modules.gaze.controller import GazeController

SCREEN = QRect(0, 0, 1000, 800)


def identity_calibration():
    pts = [(x, y) for x in (0, 500, 1000) for y in (0, 400, 800)]
    c = GazeCalibration()
    c.fit(pts, pts)  # feature == screen pixels, keeps tests readable
    return c


def sample(t, feature=(100, 100), blink=False, face=True):
    s = {"camera_ok": True, "face": face, "ts_ms": t}
    if face:
        s.update({"feature": feature, "blink": blink, "ear": 0.3})
    return s


@pytest.fixture
def button(qapp):
    b = QPushButton("Book")
    b.clicks = 0

    def on_click():
        b.clicks += 1

    b.clicked.connect(on_click)
    b.show()
    return b


@pytest.fixture
def ctrl(qapp, button):
    target = {"widget": button}
    c = GazeController(hit_test=lambda pt: target["widget"], screen_rect=SCREEN)
    c.set_calibration(identity_calibration(), error_px=50)  # dwell = 1000 ms
    c.target = target
    return c


def feed(ctrl, start, end, step=50, **kw):
    for t in range(start, end + 1, step):
        ctrl.process(sample(t, **kw))


def test_dwell_ms_follows_accuracy(ctrl):
    assert ctrl.dwell_ms == 1000


def test_dwell_clicks_button(ctrl, button):
    feed(ctrl, 0, 1000)
    assert button.clicks == 1


def test_blink_clicks_immediately(ctrl, button):
    ctrl.process(sample(0, blink=True))
    assert button.clicks == 1


def test_blink_then_stare_clicks_once(ctrl, button):
    ctrl.process(sample(0, blink=True))
    feed(ctrl, 50, 3000)
    assert button.clicks == 1


def test_no_face_resets_dwell(ctrl, button):
    feed(ctrl, 0, 600)
    ctrl.process(sample(650, face=False))
    feed(ctrl, 700, 1300)
    assert button.clicks == 0


def test_only_enabled_buttons_clicked(ctrl, button, qapp):
    button.setEnabled(False)
    feed(ctrl, 0, 1500)
    assert button.clicks == 0
    ctrl.target["widget"] = QLabel("not a button")
    feed(ctrl, 1600, 3000)  # must not raise or click anything


def test_child_of_button_resolves_to_button(ctrl, button):
    child = QWidget(button)
    ctrl.target["widget"] = child
    feed(ctrl, 0, 1000)
    assert button.clicks == 1


def test_point_clamped_to_screen(ctrl):
    points = []
    ctrl.point.connect(points.append)
    ctrl.process(sample(0, feature=(-500, 99999)))
    assert points and SCREEN.contains(points[-1])


def test_paused_does_not_click(ctrl, button):
    raw = []
    ctrl.raw_sample.connect(raw.append)
    ctrl.paused = True
    feed(ctrl, 0, 1500, blink=True)
    assert button.clicks == 0 and len(raw) == 31


def test_uncalibrated_does_nothing(qapp, button):
    c = GazeController(hit_test=lambda pt: button, screen_rect=SCREEN)
    statuses, points = [], []
    c.status.connect(statuses.append)
    c.point.connect(points.append)
    c.process(sample(0, blink=True))
    assert statuses[-1] == "Calibrate first" and not points and button.clicks == 0


class FakeTracker:
    def __init__(self, opens=True, frames=5):
        self.opens, self.frames, self.closed = opens, frames, False

    def open(self):
        return self.opens

    def read(self):
        time.sleep(0.005)
        return sample(int(time.monotonic() * 1000)) | {"frame": object()}

    def close(self):
        self.closed = True


def wait_for(cond, timeout=3.0):
    end = time.monotonic() + timeout
    while not cond() and time.monotonic() < end:
        QCoreApplication.processEvents()
        time.sleep(0.01)
    return cond()


def test_worker_thread_delivers_samples_without_frames(qapp):
    tracker = FakeTracker()
    c = GazeController(hit_test=lambda pt: None, screen_rect=SCREEN)
    raw = []
    c.raw_sample.connect(raw.append)
    c.start(tracker_factory=lambda: tracker)
    try:
        assert wait_for(lambda: len(raw) >= 3)
        assert "frame" not in raw[0]
    finally:
        c.stop()
    assert tracker.closed and not c.running


def test_camera_open_failure_reports_status(qapp):
    tracker = FakeTracker(opens=False)
    c = GazeController(hit_test=lambda pt: None, screen_rect=SCREEN)
    statuses = []
    c.status.connect(statuses.append)
    c.start(tracker_factory=lambda: tracker)
    assert wait_for(lambda: any("camera" in s.lower() for s in statuses))
    c.stop()
    assert not c.running
