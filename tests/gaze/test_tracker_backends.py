import numpy as np
import pytest

from accessshift.modules.gaze.tracker import BACKENDS, GazeTracker, create_tracker, resolve_backend


def test_resolve_backend_defaults_and_rejects_unknown(monkeypatch):
    monkeypatch.delenv("GAZE_BACKEND", raising=False)
    assert resolve_backend() == "auto"
    monkeypatch.setenv("GAZE_BACKEND", "Mediapipe")
    assert resolve_backend() == "mediapipe"
    with pytest.raises(ValueError):
        resolve_backend("tobii")
    assert set(BACKENDS) == {"auto", "mediapipe", "eyetrax", "hybrid"}


def test_create_tracker_mediapipe_forced():
    t = create_tracker(0, backend="mediapipe")
    assert isinstance(t, GazeTracker)
    assert t.backend_name == "mediapipe"


def test_create_tracker_auto_keeps_mediapipe_head_path():
    t = create_tracker(0, backend="auto")
    assert hasattr(t, "open") and hasattr(t, "read") and hasattr(t, "close")
    assert hasattr(t, "blink")
    # hybrid (EyeTrax eyes + MediaPipe head) or pure MediaPipe fallback
    assert getattr(t, "backend_name", "") in ("hybrid", "mediapipe")


def test_create_tracker_falls_back_when_hybrid_init_fails(monkeypatch):
    import types

    import accessshift.modules.gaze.tracker as tracker_mod

    class Boom:
        def __init__(self, camera_index=0):
            raise RuntimeError("no model")

    fake = types.ModuleType("accessshift.modules.gaze.hybrid_tracker")
    fake.HybridGazeTracker = Boom
    monkeypatch.setitem(__import__("sys").modules, "accessshift.modules.gaze.hybrid_tracker", fake)

    for backend in ("auto", "hybrid"):
        t = tracker_mod.create_tracker(0, backend=backend)
        assert isinstance(t, GazeTracker)


def test_eyetrax_feature_helpers_when_installed():
    from accessshift.modules.gaze import eyetrax_tracker as et

    if not et.EYETRAX_AVAILABLE:
        pytest.skip("eyetrax not installed")
    n = len(et._SUBSET)
    features = np.zeros(n * 3 + 3, dtype=float)
    li = et._SUBSET.index(468)
    ri = et._SUBSET.index(473)
    features[li * 3 : li * 3 + 2] = (0.2, -0.1)
    features[ri * 3 : ri * 3 + 2] = (0.4, 0.1)
    features[-3:] = (0.05, -0.02, 0.0)
    assert et.features_to_eye_point(features) == pytest.approx((0.3, 0.0))
    assert et.features_to_head_point(features) == pytest.approx((0.05, -0.02))
