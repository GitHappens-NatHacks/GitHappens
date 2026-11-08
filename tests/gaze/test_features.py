import pytest

from accessshift.modules.gaze.features import (
    LEFT_EYE,
    LEFT_IRIS,
    LEFT_LID_MID,
    RIGHT_EYE,
    RIGHT_IRIS,
    RIGHT_LID_MID,
    _LID_BLEND,
    _VERTICAL_GAIN,
    axis_ratio,
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


def test_axis_ratio_vertical():
    assert axis_ratio((0, 0), (0, 10), (0, 3)) == pytest.approx(0.3)


def test_gaze_feature_vertical_uses_corner_and_lid():
    points = [(0.0, 0.0)] * 478
    points = list(points)
    points[LEFT_EYE[0]], points[LEFT_EYE[3]] = (0.0, 0.0), (10.0, 0.0)
    points[LEFT_EYE[1]], points[LEFT_EYE[2]] = (5.0, -2.0), (5.0, -2.0)
    points[LEFT_EYE[4]], points[LEFT_EYE[5]] = (5.0, 8.0), (5.0, 8.0)
    points[LEFT_LID_MID[0]], points[LEFT_LID_MID[1]] = (5.0, -2.0), (5.0, 8.0)
    points[RIGHT_EYE[0]], points[RIGHT_EYE[3]] = (20.0, 0.0), (30.0, 0.0)
    points[RIGHT_EYE[1]], points[RIGHT_EYE[2]] = (25.0, -2.0), (25.0, -2.0)
    points[RIGHT_EYE[4]], points[RIGHT_EYE[5]] = (25.0, 8.0), (25.0, 8.0)
    points[RIGHT_LID_MID[0]], points[RIGHT_LID_MID[1]] = (25.0, -2.0), (25.0, 8.0)
    for i in LEFT_IRIS:
        points[i] = (5.0, 2.0)
    for i in RIGHT_IRIS:
        points[i] = (25.0, 2.0)
    expected_v = _VERTICAL_GAIN * (0.2 + _LID_BLEND * (0.4 - 0.5))
    assert gaze_feature(points) == pytest.approx((0.5, expected_v))


# --- head pointing: nose tip relative to the eyes -------------------------------------

from accessshift.modules.gaze.features import EYE_OUTER, NOSE_TIP, head_feature  # noqa: E402


def face(nose, left=(0.0, 0.0), right=(10.0, 0.0)):
    points = [(0.0, 0.0)] * 478
    points[EYE_OUTER[0]], points[EYE_OUTER[1]] = left, right
    points[NOSE_TIP] = nose
    return points


def test_head_facing_forward():
    assert head_feature(face(nose=(5.0, 6.0))) == pytest.approx((0.0, 0.6))


def test_head_turn_moves_x_and_tilt_moves_y():
    hx, hy = head_feature(face(nose=(7.0, 4.0)))
    assert hx == pytest.approx(0.2) and hy == pytest.approx(0.4)


def test_head_feature_ignores_sliding_and_distance():
    near = head_feature(face(nose=(7.0, 4.0)))
    moved = head_feature(face(nose=(107.0, 54.0), left=(100.0, 50.0), right=(110.0, 50.0)))
    closer = head_feature(face(nose=(14.0, 8.0), right=(20.0, 0.0)))  # twice as big on camera
    assert moved == pytest.approx(near) and closer == pytest.approx(near)
