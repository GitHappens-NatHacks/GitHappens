import pytest

from accessshift.modules.gaze.calibration import DotCollector

SIZE = (1000, 800)


def s(t, feature=(0.5, 0.0), ear=0.3, face=True):
    return {"ts_ms": t, "face": face, "feature": feature, "ear": ear}


def run(c, start, end, step=33, **kw):
    t = start
    while t <= end:
        c.update(s(t, **kw), ear_threshold=0.15)
        t += step
    return t


def test_steady_dot_accepted_after_settle_and_collect():
    c = DotCollector([(0.5, 0.5)], SIZE)
    run(c, 0, 2600, feature=(0.51, -0.02))
    assert c.done and c.features[0] == pytest.approx((0.51, -0.02))
    assert c.debug[0]["retries"] == 0


def test_unsteady_dot_is_retried_then_accepted_when_steady():
    c = DotCollector([(0.5, 0.5)], SIZE, max_spread=0.04, max_retries=3)
    t = 0
    for i in range(80):  # eyes jumping 0.08 back and forth past settle+collect
        c.update(s(t, feature=(0.5 + (0.08 if i % 2 else -0.08), 0.0)), 0.15)
        t += 33
    assert not c.done and c.retries == 1
    run(c, t, t + 2600)
    assert c.done and c.debug[0]["retries"] == 1


def test_force_accepts_after_max_retries():
    c = DotCollector([(0.5, 0.5)], SIZE, max_spread=0.01, max_retries=3)
    t = 0
    for _ in range(4):
        for i in range(80):
            c.update(s(t, feature=(0.5 + (0.06 if i % 2 else -0.06), 0.0)), 0.15)
            t += 33
    assert c.done
    assert c.debug[0]["retries"] == 3


def test_closed_eyes_and_no_face_not_sampled():
    c = DotCollector([(0.5, 0.5)], SIZE, max_retries=5)
    t = run(c, 0, 2600, ear=0.05)
    t = run(c, t, t + 2600, face=False)
    assert not c.done and c.retries >= 2


def test_target_px_and_progress():
    c = DotCollector([(0.1, 0.9)], SIZE)
    assert c.target_px() == (100, 720)
    c.update(s(0), 0.15)
    # settle 800 + collect 1600: halfway through collect is at 800 + 800 = 1600
    assert c.progress(0) == 0.0 and c.progress(1600) == pytest.approx(0.5) and c.progress(5000) == 1.0


def test_ears_are_kept_per_dot():
    # The head calibration tunes "closed eyes" against the narrowest held pose.
    c = DotCollector([(0.5, 0.5), (0.5, 0.9)], SIZE)
    t = run(c, 0, 2600, ear=0.3)
    run(c, t, t + 2600, ear=0.2)
    assert c.done
    assert min(c.dot_ears[0]) == 0.3 and max(c.dot_ears[1]) == 0.2
