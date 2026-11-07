from pathlib import Path

from accessshift.ui import gaze_mode
from accessshift.ui.main_window import MainWindow
from tests.gaze.test_gaze_mode import FakeTracker

ROOT = Path(__file__).resolve().parents[2]


def test_als_profile_turns_gaze_on_and_close_turns_it_off(qapp, monkeypatch):
    real_init = gaze_mode.GazeMode.__init__

    def fake_camera_init(self, parent=None, **kw):
        real_init(self, parent, tracker_factory=FakeTracker, calibrate_on_start=False)

    monkeypatch.setattr(gaze_mode.GazeMode, "__init__", fake_camera_init)
    w = MainWindow(ROOT)
    assert not w.gaze.enabled  # starts on the Parkinson's profile
    w.engine.set_profile("als")
    assert w.gaze.enabled and w.chk_gaze.isChecked()
    w.chk_gaze.setChecked(False)
    assert not w.gaze.enabled
    w.chk_gaze.setChecked(True)
    assert w.gaze.enabled
    w.close()
    assert not w.gaze.enabled
