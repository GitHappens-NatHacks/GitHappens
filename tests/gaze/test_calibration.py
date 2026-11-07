import pytest

from accessshift.modules.gaze.calibration import CALIBRATION_POINTS, GazeCalibration


def test_recovers_affine_mapping():
    feats = [(u, v) for u in (0.3, 0.5, 0.7) for v in (-0.1, 0.0, 0.1)]
    targets = [(1000 * u + 50, 2000 * v + 400) for u, v in feats]
    c = GazeCalibration()
    c.fit(feats, targets)
    assert c.is_fitted
    assert c.map((0.6, 0.05)) == pytest.approx((650, 500), abs=1e-6)
    assert c.error_px(feats, targets) == pytest.approx(0, abs=1e-6)


def test_error_px_is_mean_distance():
    feats = [(u, v) for u in (0.3, 0.5, 0.7) for v in (-0.1, 0.0, 0.1)]
    targets = [(1000 * u, 1000 * v) for u, v in feats]
    c = GazeCalibration()
    c.fit(feats, targets)
    shifted = [(x + 3, y + 4) for x, y in targets]  # every point 5 px away
    assert c.error_px(feats, shifted) == pytest.approx(5.0)


def test_too_few_points_raises():
    with pytest.raises(ValueError):
        GazeCalibration().fit([(0, 0)] * 2, [(0, 0)] * 2)


def test_length_mismatch_raises():
    with pytest.raises(ValueError):
        GazeCalibration().fit([(0, 0)] * 9, [(0, 0)] * 8)


def test_map_before_fit_raises():
    c = GazeCalibration()
    assert not c.is_fitted
    with pytest.raises(RuntimeError):
        c.map((0.5, 0.0))


def test_nine_points():
    assert len(CALIBRATION_POINTS) == 9
    assert CALIBRATION_POINTS[0] == (0.1, 0.1)
    assert CALIBRATION_POINTS[1] == (0.5, 0.1)  # row-major
    assert CALIBRATION_POINTS[-1] == (0.9, 0.9)


# Real webcam calibration (2026-11-07, 1470x956 screen) with its two noisy dots removed.
# A 6-term quadratic fits these 7 points almost exactly and then predicts ~20,000 px off.
REAL_CAL = [
    ((0.1, 0.1), (0.4827, -0.0652)),
    ((0.5, 0.1), (0.5169, -0.0539)),
    ((0.9, 0.1), (0.5579, -0.0567)),
    ((0.5, 0.5), (0.5449, -0.0387)),
    ((0.9, 0.5), (0.5398, -0.0387)),
    ((0.1, 0.9), (0.5367, -0.0376)),
    ((0.5, 0.9), (0.5377, -0.0380)),
]
REAL_VAL = [
    ((0.3, 0.3), (0.5062, -0.0467)),
    ((0.7, 0.3), (0.5263, -0.0515)),
    ((0.3, 0.7), (0.5097, -0.0599)),
    ((0.7, 0.7), (0.5370, -0.0391)),
]


def test_noisy_real_calibration_stays_usable():
    w, h = 1470, 956
    c = GazeCalibration()
    c.fit([f for _, f in REAL_CAL], [(x * w, y * h) for (x, y), _ in REAL_CAL])
    err = c.error_px([f for _, f in REAL_VAL], [(x * w, y * h) for (x, y), _ in REAL_VAL])
    assert err < 600
