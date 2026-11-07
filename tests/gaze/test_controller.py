import time

import pytest
from PySide6.QtCore import QCoreApplication, QPoint, QRect
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
        s.update({"feature": feature, "head": feature, "blink": blink, "ear": 0.3})
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
    c.set_calibration(identity_calibration(), error_px=50)  # dwell = 2150 ms
    c.hit = target
    return c


def feed(ctrl, start, end, step=50, **kw):
    for t in range(start, end + 1, step):
        ctrl.process(sample(t, **kw))


def test_dwell_ms_follows_accuracy(ctrl):
    assert ctrl.dwell_ms == 2150


def test_dwell_clicks_button(ctrl, button):
    feed(ctrl, 0, 2200)
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
    ctrl.hit["widget"] = QLabel("not a button")
    feed(ctrl, 1600, 3000)  # must not raise or click anything


def test_child_of_button_resolves_to_button(ctrl, button):
    child = QWidget(button)
    ctrl.hit["widget"] = child
    feed(ctrl, 0, 2200)
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


# --- snap to nearest button (gaze accuracy is ~±250 px; portal buttons are ~64 px tall) ---

def make_button(qapp, x, y, w=300, h=64, text="B"):
    b = QPushButton(text)
    b.setGeometry(x, y, w, h)
    b.clicks = 0

    def on_click():
        b.clicks += 1

    b.clicked.connect(on_click)
    b.show()
    return b


@pytest.fixture
def two_buttons(qapp):
    a = make_button(qapp, 100, 100, text="A")  # centre (250, 132)
    b = make_button(qapp, 100, 400, text="B")  # centre (250, 432)
    yield a, b
    a.close()
    b.close()


def snapping_ctrl(buttons, error_px=150):
    c = GazeController(hit_test=lambda pt: None, screen_rect=SCREEN, buttons=lambda: list(buttons))
    c.set_calibration(identity_calibration(), error_px=error_px)
    return c


def test_snaps_to_nearest_button_within_accuracy(two_buttons):
    a, b = two_buttons
    c = snapping_ctrl(two_buttons)
    # error 150 -> dwell 2450 ms
    feed(c, 0, 2600, feature=(250, 230))  # 66 px below A, 170 px above B
    assert a.clicks == 1 and b.clicks == 0


def test_no_snap_beyond_accuracy(two_buttons):
    a, b = two_buttons
    c = snapping_ctrl(two_buttons, error_px=100)
    feed(c, 0, 2600, feature=(900, 700))
    assert a.clicks == 0 and b.clicks == 0


def test_target_is_sticky_against_small_jitter(two_buttons):
    a, b = two_buttons
    c = snapping_ctrl(two_buttons, error_px=200)
    targets = []
    c.target.connect(targets.append)
    feed(c, 0, 500, feature=(250, 250))  # nearer A (distance 86 vs 150)
    feed(c, 550, 1500, feature=(250, 285))  # now nearer B by 6 px (121 vs 115): keep A
    assert targets[-1] == QRect(a.mapToGlobal(QPoint(0, 0)), a.size())
    feed(c, 1550, 3000, feature=(250, 380))  # clearly nearer B, held: switch
    assert targets[-1] == QRect(b.mapToGlobal(QPoint(0, 0)), b.size())


def test_exact_hit_still_wins(qapp, button):
    other = make_button(qapp, 0, 0, text="other")
    c = GazeController(hit_test=lambda pt: button, screen_rect=SCREEN, buttons=lambda: [other])
    c.set_calibration(identity_calibration(), error_px=500)  # dwell 3500 ms
    feed(c, 0, 3600, feature=(5, 5))
    assert button.clicks == 1 and other.clicks == 0
    other.close()


def test_target_cleared_when_gaze_moves_away_or_face_lost(two_buttons):
    c = snapping_ctrl(two_buttons, error_px=50)
    targets = []
    c.target.connect(targets.append)
    c.process(sample(0, feature=(250, 130)))  # on A
    assert not targets[-1].isNull()
    feed(c, 50, 2000, feature=(900, 700))  # far from everything, held past the grace period
    assert targets[-1] == QRect()
    feed(c, 2050, 3000, feature=(250, 130))
    c.process(sample(3050, face=False))
    assert targets[-1] == QRect()


# --- steadier gaze -------------------------------------------------------------------

def test_jittery_gaze_is_smoothed(ctrl):
    import random
    import statistics

    random.seed(1)
    points = []
    ctrl.point.connect(points.append)
    for t in range(0, 3000, 33):  # 30 fps, +/-60 px webcam jitter around (500, 400)
        ctrl.process(sample(t, feature=(500 + random.uniform(-60, 60), 400 + random.uniform(-60, 60))))
    settled = points[30:]
    assert statistics.pstdev(p.x() for p in settled) < 12
    assert statistics.pstdev(p.y() for p in settled) < 12


def test_eyes_closed_freezes_point_and_dwell(ctrl, button):
    points = []
    ctrl.point.connect(points.append)
    feed(ctrl, 0, 500)
    n = len(points)
    for t in range(550, 1600, 50):  # eyes closed: garbage features, no movement, no click
        ctrl.process(sample(t, feature=(900, 700)) | {"closed_ms": t - 500})
    assert len(points) == n and button.clicks == 0


def test_eyes_closed_three_seconds_requests_exit(ctrl, button):
    exits, progress = [], []
    ctrl.exit_requested.connect(lambda: exits.append(1))
    ctrl.exit_progress.connect(progress.append)
    for t in range(0, 3600, 100):
        ctrl.process(sample(t) | {"closed_ms": t})
    assert exits == [1]  # once per closure
    assert progress and max(progress) == 1.0
    ctrl.process(sample(3700))  # eyes open again
    assert progress[-1] == 0.0 and button.clicks == 0


def test_short_closure_does_not_exit(ctrl):
    exits = []
    ctrl.exit_requested.connect(lambda: exits.append(1))
    for t in range(0, 1400, 100):
        ctrl.process(sample(t) | {"closed_ms": t})
    ctrl.process(sample(1500))
    assert exits == []


def test_natural_blink_pauses_dwell_without_restart_or_click(ctrl, button):
    feed(ctrl, 0, 600)
    for t in (650, 700, 750):  # 150 ms natural blink
        ctrl.process(sample(t) | {"closed_ms": t - 650 + 1})
    feed(ctrl, 800, 2000)
    assert button.clicks == 0  # the 150 ms with eyes shut didn't count
    feed(ctrl, 2050, 2400)
    assert button.clicks == 1  # earlier open time plus later stare reaches dwell



# --- head or eyes as the pointer -------------------------------------------------------

def test_default_source_is_head(qapp):
    assert GazeController(hit_test=lambda p: None, screen_rect=SCREEN).source == "head"


def test_head_source_points_with_head_feature(ctrl):
    ctrl.set_source("head")
    ctrl.set_calibration(identity_calibration(), error_px=50)
    points, raw = [], []
    ctrl.point.connect(points.append)
    ctrl.raw_sample.connect(raw.append)
    ctrl.process(sample(0, feature=(900, 700)) | {"head": (100, 120)})
    assert (points[-1].x(), points[-1].y()) == (100, 120)
    assert raw[-1]["feature"] == (100, 120)  # calibration sees the active source


def test_eyes_source_points_with_eye_feature(ctrl):
    ctrl.set_source("eyes")
    ctrl.set_calibration(identity_calibration(), error_px=50)
    points = []
    ctrl.point.connect(points.append)
    ctrl.process(sample(0, feature=(300, 200)) | {"head": (100, 120)})
    assert (points[-1].x(), points[-1].y()) == (300, 200)


def test_switching_source_needs_new_calibration(ctrl):
    ctrl.set_source("eyes")
    ctrl.set_calibration(identity_calibration(), error_px=50)
    ctrl.set_source("head")
    assert not ctrl.calibration.is_fitted
    with pytest.raises(ValueError):
        ctrl.set_source("nose")


# --- head mode: rest zone in the middle, nothing selected while facing forward --------------

def test_head_rest_zone_selects_nothing_until_you_turn(qapp, button):
    from accessshift.modules.gaze.calibration import head_calibration

    poses = {"center": (0.0, 0.6), "left": (-0.2, 0.6), "right": (0.2, 0.6), "up": (0.0, 0.45), "down": (0.0, 0.75)}
    c = GazeController(hit_test=lambda pt: button, screen_rect=SCREEN)  # a button everywhere
    c.set_calibration(head_calibration(poses, (SCREEN.width(), SCREEN.height())), error_px=150)
    for t in range(0, 4000, 33):
        c.process({"face": True, "ts_ms": t, "head": poses["center"], "feature": (0, 0), "ear": 0.3, "blink": False})
    assert button.clicks == 0  # facing forward = resting
    for t in range(4000, 7000, 33):
        c.process({"face": True, "ts_ms": t, "head": (0.15, 0.6), "feature": (0, 0), "ear": 0.3, "blink": False})
    assert button.clicks == 1
