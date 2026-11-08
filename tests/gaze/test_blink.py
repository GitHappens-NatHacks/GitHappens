import pytest

from accessshift.modules.gaze.blink import BlinkDetector, eye_aspect_ratio


def feed(det, samples):
    return [det.update(ear, ts) for ear, ts in samples]


def test_deliberate_blink_fires_on_reopen():
    d = BlinkDetector()
    out = feed(d, [(0.3, 0), (0.1, 100), (0.1, 300), (0.1, 550), (0.3, 570)])
    assert out == [False, False, False, False, True]


def test_natural_blink_ignored():  # ~120 ms closure
    d = BlinkDetector()
    assert not any(feed(d, [(0.3, 0), (0.1, 100), (0.1, 180), (0.3, 220)]))


def test_long_closure_ignored():  # eyes resting for 3 s
    d = BlinkDetector()
    assert not any(feed(d, [(0.3, 0), (0.1, 100), (0.1, 3100), (0.3, 3150)]))


def test_cooldown_blocks_second_blink():
    d = BlinkDetector()
    out = feed(d, [(0.1, 0), (0.3, 400), (0.1, 450), (0.3, 850)])
    assert out == [False, True, False, False]


def test_calibrate_open_sets_threshold():
    d = BlinkDetector()
    d.calibrate_open([0.30, 0.32, 0.28])
    assert d.ear_threshold == pytest.approx(0.225)


def test_calibrate_open_ignores_empty():
    d = BlinkDetector()
    d.calibrate_open([])
    assert d.ear_threshold == pytest.approx(0.21)


def test_eye_aspect_ratio_unchanged():
    eye = [(0, 0), (3, -1), (7, -1), (10, 0), (7, 1), (3, 1)]
    assert eye_aspect_ratio(eye) == pytest.approx(0.2)


def test_closed_ms_reports_current_closure():
    d = BlinkDetector()
    d.update(0.3, 0)
    assert d.closed_ms(0) == 0
    d.update(0.1, 100)
    assert d.closed_ms(2600) == 2500
    d.update(0.3, 2700)
    assert d.closed_ms(2700) == 0
