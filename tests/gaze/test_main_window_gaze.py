from pathlib import Path

from accessshift.ui import gaze_mode
from accessshift.ui.main_window import MainWindow
from tests.gaze.test_gaze_mode import FakeTracker

ROOT = Path(__file__).resolve().parents[2]


def test_als_profile_turns_gaze_on_and_close_turns_it_off(qapp, monkeypatch):
    from accessshift.ui.control_center_settings import AccessibilitySettings

    real_init = gaze_mode.GazeMode.__init__

    def fake_camera_init(self, parent=None, **kw):
        real_init(self, parent, tracker_factory=FakeTracker, calibrate_on_start=False)

    monkeypatch.setattr(gaze_mode.GazeMode, "__init__", fake_camera_init)
    # Ignore leftover QSettings from prior app runs (gaze may already be on).
    monkeypatch.setattr(
        "accessshift.ui.control_center.load_settings",
        lambda store=None: AccessibilitySettings(profile="parkinsons"),
    )
    w = MainWindow(ROOT)
    w._apply_profile("parkinsons")
    assert not w.gaze.enabled
    w._apply_profile("als")
    assert w.gaze.enabled and w.chk_gaze.isChecked()
    w.chk_gaze.setChecked(False)
    assert not w.gaze.enabled
    w.chk_gaze.setChecked(True)
    assert w.gaze.enabled
    w.close()
    assert not w.gaze.enabled


def test_gaze_focus_mode_hides_sidebar_and_exit_button_turns_gaze_off(qapp, monkeypatch):
    real_init = gaze_mode.GazeMode.__init__

    def fake_camera_init(self, parent=None, **kw):
        real_init(self, parent, tracker_factory=FakeTracker, calibrate_on_start=False)

    monkeypatch.setattr(gaze_mode.GazeMode, "__init__", fake_camera_init)
    w = MainWindow(ROOT)
    w.show()
    w.engine.set_profile("custom")  # all modules off: complex portal, sidebar visible
    assert w.sidebar.isVisible() and not w.gaze_bar.isVisible()
    assert w.portal.mode.value == "complex"

    w.chk_gaze.setChecked(True)
    assert not w.sidebar.isVisible() and w.gaze_bar.isVisible()
    assert w.portal.mode.value == "accessible"  # focus on the simple booking flow

    w.btn_exit_gaze.click()  # what a dwell/blink on "Exit gaze control" does
    assert not w.gaze.enabled and not w.chk_gaze.isChecked()
    assert w.sidebar.isVisible() and not w.gaze_bar.isVisible()
    assert w.portal.mode.value == "complex"
    w.close()


def test_exit_by_closing_eyes_and_wide_exit_button(qapp, monkeypatch):
    real_init = gaze_mode.GazeMode.__init__

    def fake_camera_init(self, parent=None, **kw):
        real_init(self, parent, tracker_factory=FakeTracker, calibrate_on_start=False)

    monkeypatch.setattr(gaze_mode.GazeMode, "__init__", fake_camera_init)
    w = MainWindow(ROOT)
    w.resize(1200, 800)
    w.show()
    w.chk_gaze.setChecked(True)
    qapp.processEvents()
    assert w.btn_exit_gaze.width() >= 0.35 * w.gaze_bar.width()
    assert w.btn_exit_gaze.height() >= 96

    w.gaze.controller.exit_requested.emit()  # eyes held closed for 3 s
    assert not w.gaze.enabled and not w.chk_gaze.isChecked() and w.sidebar.isVisible()
    w.close()


def test_gaze_mode_shows_grid_and_head_eyes_switch(qapp, monkeypatch):
    real_init = gaze_mode.GazeMode.__init__

    def fake_camera_init(self, parent=None, **kw):
        real_init(self, parent, tracker_factory=FakeTracker, calibrate_on_start=False)

    monkeypatch.setattr(gaze_mode.GazeMode, "__init__", fake_camera_init)
    w = MainWindow(ROOT)
    w.show()
    w.chk_gaze.setChecked(True)
    assert w.gaze_grid.isVisible() and not w.portal.isVisible()
    assert [b.text() for b in w.gaze_grid.visible_squares()] == ["Myself", "Someone I care for"]

    assert w.gaze.controller.source == "head" and "Head" in w.btn_gaze_source.text()
    w.btn_gaze_source.click()
    assert w.gaze.controller.source == "eyes" and "Eyes" in w.btn_gaze_source.text()

    w.chk_gaze.setChecked(False)
    # Back to purple Control Center: focus host (portal/grid) is hidden.
    assert w.sidebar.isVisible() and w.workspace.isVisible()
    assert not w.gaze_grid.isVisible() and not w.gaze_bar.isVisible()
    w.close()
