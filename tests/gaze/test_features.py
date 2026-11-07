import pytest

from accessshift.modules.gaze.features import (
    LEFT_EYE,
    LEFT_IRIS,
    RIGHT_EYE,
    RIGHT_IRIS,
    gaze_feature,
    iris_ratio,
)


def test_iris_centered():
    assert iris_ratio((0, 0), (10, 0), (5, 0)) == pytest.approx((0.5, 0.0))


def test_iris_toward_corner_b_and_down():
    u, v = iris_ratio((0, 0), (10, 0), (8, 2))
    assert u == pytest.approx(0.8) and v == pytest.approx(0.2)


def test_translation_invariant():
    a = iris_ratio((0, 0), (10, 0), (3, 1))
    b = iris_ratio((100, 50), (110, 50), (103, 51))
    assert a == pytest.approx(b)


def test_zero_width_eye_returns_center():
    assert iris_ratio((5, 5), (5, 5), (5, 5)) == (0.5, 0.0)


def test_gaze_feature_averages_both_eyes():
    points = [(0.0, 0.0)] * 478
    points = list(points)
    # left eye: corners (0,0)-(10,0), iris at u=0.2 ; right eye: corners (20,0)-(30,0), iris at u=0.6
    points[LEFT_EYE[0]], points[LEFT_EYE[3]] = (0.0, 0.0), (10.0, 0.0)
    points[RIGHT_EYE[0]], points[RIGHT_EYE[3]] = (20.0, 0.0), (30.0, 0.0)
    for i in LEFT_IRIS:
        points[i] = (2.0, 1.0)
    for i in RIGHT_IRIS:
        points[i] = (26.0, 1.0)
    assert gaze_feature(points) == pytest.approx((0.4, 0.1))
