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


def sample(t, feature=(100, 100), blink=False, face=True, ear=0.3):
    s = {"camera_ok": True, "face": face, "ts_ms": t}
    if face:
        s.update({"feature": feature, "head": feature, "blink": blink, "ear": ear})
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
    c.set_source("eyes")
    c.set_dwell_ms(3000)  # these timing tests use a slow 3 s selection speed
    c.set_calibration(identity_calibration(), error_px=50)
    c.hit = target
    return c


def feed(ctrl, start, end, step=50, **kw):
    for t in range(start, end + 1, step):
        ctrl.process(sample(t, **kw))


def test_dwell_ms_is_uniform(ctrl):
    from accessshift.modules.gaze.dwell import UNIFORM_DWELL_MS

    assert ctrl.dwell_ms == 3000  # the chosen speed, whatever the accuracy
    ctrl.set_calibration(identity_calibration(), error_px=500)
    assert ctrl.dwell_ms == 3000
    ctrl.set_dwell_ms(None)  # no chosen speed: the default ("Normal")
    assert ctrl.dwell_ms == UNIFORM_DWELL_MS


def test_dwell_clicks_button(ctrl, button):
    feed(ctrl, 0, 3000)
    assert button.clicks == 1


def test_blink_ignored_before_ring_starts(ctrl, button):
    ctrl.process(sample(0, blink=True))
    assert button.clicks == 0


def test_blink_clicks_after_ring_starts(ctrl, button):
    feed(ctrl, 0, 700)  # ~23% of 3000 ms
    ctrl.process(sample(750, blink=True))
    assert button.clicks == 1


def test_blink_then_stare_clicks_once(ctrl, button):
    feed(ctrl, 0, 700)
    ctrl.process(sample(750, blink=True))
    feed(ctrl, 800, 3000)
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
    feed(ctrl, 0, 3000)
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
    c.set_source("eyes")
    c.set_calibration(identity_calibration(), error_px=150)
    # 66 px below A, 170 px above B
    feed(c, 0, 3200, feature=(250, 230))
    assert a.clicks == 1 and b.clicks == 0


def test_no_snap_beyond_accuracy(two_buttons):
    a, b = two_buttons
    c = snapping_ctrl(two_buttons, error_px=100)
    c.set_source("eyes")
    c.set_calibration(identity_calibration(), error_px=100)
    feed(c, 0, 3200, feature=(900, 700))
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
    c.set_source("eyes")
    c.set_calibration(identity_calibration(), error_px=500)
    feed(c, 0, 3200, feature=(5, 5))
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
    ctrl.set_source("eyes")  # eye features are garbage while closed
    ctrl.set_calibration(identity_calibration(), error_px=50)
    points = []
    ctrl.point.connect(points.append)
    feed(ctrl, 0, 500)
    n = len(points)
    for t in range(550, 1600, 50):  # eyes closed: garbage features, no movement, no click
        ctrl.process(sample(t, feature=(900, 700)) | {"closed_ms": t - 500})
    assert len(points) == n and button.clicks == 0


def test_eyes_closed_five_seconds_requests_exit(ctrl, button):
    exits, progress = [], []
    ctrl.exit_requested.connect(lambda: exits.append(1))
    ctrl.exit_progress.connect(progress.append)
    for t in range(0, 5600, 100):
        ctrl.process(sample(t) | {"closed_ms": t, "ear": 0.05})
    assert exits == [1]  # once per closure
    assert progress and max(progress) == 1.0
    ctrl.process(sample(5700, ear=0.3))
    assert progress[-1] == 0.0 and button.clicks == 0


def test_short_closure_does_not_exit(ctrl):
    exits = []
    ctrl.exit_requested.connect(lambda: exits.append(1))
    for t in range(0, 2000, 100):
        ctrl.process(sample(t) | {"closed_ms": t, "ear": 0.05})
    ctrl.process(sample(2100, ear=0.3))
    assert exits == []


def test_natural_blink_pauses_dwell_without_restart_or_click(ctrl, button):
    ctrl.set_source("eyes")
    ctrl.set_calibration(identity_calibration(), error_px=50)
    feed(ctrl, 0, 600)
    for t in (650, 700, 750):  # 150 ms natural blink
        ctrl.process(sample(t) | {"closed_ms": t - 650 + 1})
    feed(ctrl, 800, 2500)
    assert button.clicks == 0  # the 150 ms with eyes shut didn't count
    feed(ctrl, 2550, 3200)
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
    # Head dwell is at least 3000 ms after leaving the rest zone.
    for t in range(4000, 7500, 33):
        c.process({"face": True, "ts_ms": t, "head": (0.15, 0.6), "feature": (0, 0), "ear": 0.3, "blink": False})
    assert button.clicks == 1


def test_blink_select_can_be_turned_off(ctrl, button):
    ctrl.blink_select = False
    ctrl.process(sample(0, blink=True))
    assert button.clicks == 0


def test_user_dwell_time_overrides_automatic(ctrl, button):
    ctrl.set_dwell_ms(1500)
    ctrl.set_calibration(identity_calibration(), error_px=0)  # would be 800 ms automatically
    assert ctrl.dwell_ms == 1500
    feed(ctrl, 0, 1400)
    assert button.clicks == 0
    feed(ctrl, 1450, 1600)
    assert button.clicks == 1



def test_head_mode_keeps_pointing_but_pauses_dwell_while_eyes_closed(ctrl, button):
    # Head pointing stays valid with closed eyes, but closing your eyes (e.g. to exit)
    # must never click the option you happen to be pointing at.
    ctrl.set_source("head")
    ctrl.set_calibration(identity_calibration(), error_px=50)
    points = []
    ctrl.point.connect(points.append)
    for t in range(0, 2000, 50):
        # really closed: very low eye openness (a head-tilt dip stays above HEAD_CLOSED_EAR)
        ctrl.process(sample(t, feature=(100 + t // 10, 100)) | {"closed_ms": t + 1, "ear": 0.08})
    assert len(points) > 30 and points[-1].x() > points[0].x()  # dot kept moving
    assert button.clicks == 0
    feed(ctrl, 2050, 5200, feature=(300, 100))  # eyes open again: dwell works (3 s test speed)
    assert button.clicks == 1


def test_deleted_target_button_is_dropped_not_crashing(qapp):
    # e.g. the Head/Eye chooser popup closes while one of its buttons was targeted
    from shiboken6 import delete

    doomed = QPushButton("Head pointing")
    doomed.setGeometry(100, 100, 300, 100)
    doomed.show()
    c = GazeController(hit_test=lambda pt: None, screen_rect=SCREEN, buttons=lambda: [b for b in [doomed] if b])
    c.set_dwell_ms(3000)
    c.set_calibration(identity_calibration(), error_px=150)
    targets = []
    c.target.connect(targets.append)
    feed(c, 0, 300, feature=(250, 150))
    assert c.current_target is doomed
    delete(doomed)  # the C++ widget is gone; the Python object is a dead shell
    c._buttons = lambda: []
    feed(c, 350, 1500, feature=(250, 150))  # must not raise
    assert c.current_target is None and targets[-1] == QRect()


def test_open_popup_blocks_gaze_selection_behind_it(qapp, button):
    # e.g. the booking confirmation is open: gaze must not press "Back" behind it
    from PySide6.QtWidgets import QDialog, QVBoxLayout

    popup = QDialog()
    popup.setModal(True)
    popup_btn = QPushButton("Close", popup)
    QVBoxLayout(popup).addWidget(popup_btn)
    popup.setGeometry(600, 500, 300, 200)
    popup.show()
    qapp.processEvents()
    c = GazeController(hit_test=lambda pt: button, screen_rect=SCREEN)  # gaze sits on the background button
    c.set_dwell_ms(1000)
    c.set_calibration(identity_calibration(), error_px=0)  # exact hits only
    feed(c, 0, 1500, feature=(100, 100))
    assert button.clicks == 0
    popup.close()
    qapp.processEvents()
    feed(c, 1550, 3000, feature=(100, 100))
    assert button.clicks == 1  # popup gone: background works again


def test_popup_buttons_stay_selectable_by_gaze(qapp):
    from PySide6.QtWidgets import QDialog, QVBoxLayout

    popup = QDialog()
    popup.setModal(True)
    popup_btn = QPushButton("Start over", popup)
    QVBoxLayout(popup).addWidget(popup_btn)
    popup.show()
    qapp.processEvents()
    clicks = []
    popup_btn.clicked.connect(lambda: clicks.append(1))
    c = GazeController(hit_test=lambda pt: popup_btn, screen_rect=SCREEN)
    c.set_dwell_ms(1000)
    c.set_calibration(identity_calibration(), error_px=0)
    feed(c, 0, 1200, feature=(100, 100))
    assert clicks == [1]
    popup.close()


# --- only the hands-free window (and its popups) can be targeted ---

def test_buttons_outside_scope_window_are_ignored(qapp):
    """A button in another window (e.g. the settings page's 'Stop head control' hidden
    behind the booking window) must never be targeted."""
    booking = QWidget()
    inside = QPushButton("Myself", booking)
    inside.setGeometry(0, 0, 300, 64)
    other = make_button(qapp, 100, 100, text="Stop head control")  # a separate window
    booking.show()
    c = GazeController(hit_test=lambda pt: other, screen_rect=SCREEN,
                       buttons=lambda: [inside, other])
    c.scope = booking
    c.set_calibration(identity_calibration(), error_px=150)
    for t in range(0, 400, 50):
        c.process(sample(t, feature=(250, 132)))  # right on top of `other`
    assert c.current_target is not other
    booking.close()
    other.close()


def test_popup_of_scope_window_is_allowed(qapp):
    from PySide6.QtWidgets import QDialog

    booking = QWidget()
    booking.show()
    popup = QDialog(booking)
    close = QPushButton("Close", popup)
    popup.show()
    c = GazeController(hit_test=lambda pt: close, screen_rect=SCREEN, buttons=lambda: [close])
    c.scope = booking
    c.set_calibration(identity_calibration(), error_px=150)
    for t in range(0, 400, 50):
        c.process(sample(t, feature=(250, 132)))
    assert c.current_target is close
    popup.close()
    booking.close()


@pytest.mark.parametrize("source", ["head", "eyes"])
@pytest.mark.parametrize("speed_ms", [1600, 1100, 800])
def test_chosen_speed_applies_to_head_and_eyes(qapp, button, source, speed_ms):
    c = GazeController(hit_test=lambda pt: button, screen_rect=SCREEN)
    c.set_source(source)
    c.set_dwell_ms(speed_ms)
    c.set_calibration(identity_calibration(), error_px=50)
    feed_at = (100, 100) if source == "eyes" else (50, 50)  # head: outside the centre rest zone
    for t in range(0, speed_ms - 150, 50):
        c.process(sample(t, feature=feed_at))
    assert button.clicks == 0, "clicked before the chosen speed"
    for t in range(speed_ms - 150, speed_ms + 400, 50):
        c.process(sample(t, feature=feed_at))
    assert button.clicks == 1
