import pytest

from accessshift.modules.gaze.calibration import DotCollector

SIZE = (1000, 800)


def s(t, feature=(0.5, 0.0), ear=0.3, face=True):
    return {"ts_ms": t, "face": face, "feature": feature, "ear": ear}


def run(c, start, end, step=33, **kw):
    t = start
    while t <= end:
        c.update(s(t, **kw), ear_threshold=0.2)
        t += step
    return t


def test_steady_dot_accepted_after_settle_and_collect():
    c = DotCollector([(0.5, 0.5)], SIZE)
    run(c, 0, 1600, feature=(0.51, -0.02))
    assert c.done and c.features[0] == pytest.approx((0.51, -0.02))
    assert c.debug[0]["retries"] == 0


def test_unsteady_dot_is_retried():
    c = DotCollector([(0.5, 0.5)], SIZE)
    t = 0
    for i in range(46):  # eyes jumping 0.05 back and forth
        c.update(s(t, feature=(0.5 + (0.05 if i % 2 else -0.05), 0.0)), 0.2)
        t += 33
    run(c, t, t + 1600)
    assert c.done and c.debug[0]["retries"] == 1


def test_closed_eyes_and_no_face_not_sampled():
    c = DotCollector([(0.5, 0.5)], SIZE)
    t = run(c, 0, 1600, ear=0.1)
    t = run(c, t, t + 1600, face=False)
    assert not c.done and c.retries >= 2


def test_target_px_and_progress():
    c = DotCollector([(0.1, 0.9)], SIZE)
    assert c.target_px() == (100, 720)
    c.update(s(0), 0.2)
    assert c.progress(0) == 0.0 and c.progress(1000) == pytest.approx(0.5) and c.progress(5000) == 1.0


def test_ears_are_kept_per_dot():
    c = DotCollector([(0.5, 0.5), (0.5, 0.9)], SIZE)
    t = run(c, 0, 1600, ear=0.3)
    run(c, t, t + 1600, ear=0.2)
    assert c.done
    assert min(c.dot_ears[0]) == 0.3 and max(c.dot_ears[1]) == 0.2
