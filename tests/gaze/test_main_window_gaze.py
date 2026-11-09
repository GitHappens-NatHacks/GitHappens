"""GazeControl inside Elizabeth's control center (main_window.MainWindow on main)."""

from pathlib import Path

import pytest

import accessshift.ui.control_center as control_center
from accessshift.ui import gaze_mode
from accessshift.ui.control_center_settings import AccessibilitySettings
from accessshift.ui.gaze_booking_window import GazeBookingWindow
from accessshift.ui.main_window import MainWindow
from tests.gaze.test_gaze_mode import FakeTracker

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def window(qapp, monkeypatch):
    # Never touch the person's saved settings; never open the real camera.
    monkeypatch.setattr(control_center, "load_settings", lambda: AccessibilitySettings(initial_setup_complete=True))
    monkeypatch.setattr(control_center, "save_settings", lambda _prefs: None)
    real_init = gaze_mode.GazeMode.__init__

    def fake_camera_init(self, parent=None, **kw):
        real_init(self, parent, tracker_factory=FakeTracker, calibrate_on_start=False)

    monkeypatch.setattr(gaze_mode.GazeMode, "__init__", fake_camera_init)
    w = MainWindow(ROOT)
    w.show()
    yield w
    w.close()


def test_gaze_is_off_at_start(window):
    assert window.gaze_window is None


def test_eye_navigation_toggle_opens_gaze_booking_window(window):
    window._change_module("gaze_control", True)
    gw = window.gaze_window
    assert gw is not None and gw.isVisible() and gw.gaze.enabled
    assert [b.text() for b in gw.grid.visible_squares()] == ["Myself", "Someone I care for"]
    window._change_module("gaze_control", False)
    assert not gw.isVisible() and not gw.gaze.enabled


def test_hands_free_profile_turns_gaze_on(window):
    window._apply_profile("als")
    assert window.gaze_window is not None and window.gaze_window.gaze.enabled
    window._apply_profile("parkinsons")
    assert not window.gaze_window.gaze.enabled


def test_unrelated_setting_changes_do_not_restart_the_camera(window):
    window._change_module("gaze_control", True)
    controller = window.gaze_window.gaze.controller
    thread = controller._thread
    window._change_option("gaze_dwell_ms", 1500)
    window._change_module("steady_hand", True)
    assert controller._thread is thread  # same camera thread, never stopped


def test_close_on_booked_popup_turns_head_control_off(window):
    window._change_module("gaze_control", True)
    window.gaze_window.portal.booking_finished.emit("close")  # Close on the booked popup
    assert not window.prefs.gaze_control and not window.gaze_window.gaze.enabled
    assert not window.gaze_window.isVisible()


def test_closing_eyes_exits_too(window):
    window._change_module("gaze_control", True)
    window.gaze_window.gaze.controller.exit_requested.emit()
    assert not window.prefs.gaze_control and not window.gaze_window.isVisible()


def test_closing_the_gaze_window_turns_eye_navigation_off(window):
    window._change_module("gaze_control", True)
    window.gaze_window.close()
    assert not window.prefs.gaze_control and not window.gaze_window.gaze.enabled


def test_calibration_button_runs_gaze_calibration_not_a_placeholder(window, monkeypatch):
    calls = []
    monkeypatch.setattr(GazeBookingWindow, "recalibrate", lambda self: calls.append(1))
    window._request_calibration()
    assert window.prefs.gaze_control and window.gaze_window.isVisible() and calls == [1]


def test_gaze_window_points_with_the_head_only(window, qapp):
    window._change_module("gaze_control", True)
    gw = window.gaze_window
    qapp.processEvents()
    assert gw.gaze.controller.source == "head" and not gw.btn_source.isVisible()


def test_closing_main_window_releases_camera(window):
    window._change_module("gaze_control", True)
    gw = window.gaze_window
    window.close()
    assert not gw.gaze.enabled


# --- head movement page in the control center -------------------------------------------------

def visible_texts(widget):
    from PySide6.QtWidgets import QLabel, QPushButton

    return [w.text() for kind in (QLabel, QPushButton) for w in widget.findChildren(kind)]


def test_page_is_head_movement_with_no_placeholder_text(window):
    texts = visible_texts(window)
    joined = "\n".join(texts)
    assert "integration pending" not in joined.lower()
    assert "Eye & blink" not in joined and "Adnan" not in joined
    assert any("Head movement control" in t for t in texts)


def test_no_em_dashes_in_any_message(window):
    from accessshift.modules.gaze import controller
    from accessshift.ui import gaze_mode as gm

    window._change_module("gaze_control", True)
    texts = visible_texts(window) + visible_texts(window.gaze_window)
    texts += [controller.STATUS_NO_FACE, controller.STATUS_UNCALIBRATED, gm.EXIT_HINT]
    assert not [t for t in texts if "—" in t]


def test_blink_and_dwell_settings_drive_head_control(window):
    window._change_module("gaze_control", True)
    ctrl = window.gaze_window.gaze.controller
    window._change_option("gaze_dwell_ms", 1700)
    assert ctrl.dwell_ms == 1700
    window._change_option("blink_select", False)
    assert ctrl.blink_select is False


def test_gaze_window_uses_app_colours_and_follows_theme(window):
    from accessshift.ui.theme import gaze_palette

    PALETTES = {name: gaze_palette(name) for name in ("standard", "high_contrast")}

    window._change_module("gaze_control", True)
    gw = window.gaze_window
    assert PALETTES["standard"].background.lower() in gw.styleSheet().lower()
    window._change_option("color_profile", "high_contrast")
    assert PALETTES["high_contrast"].background.lower() in gw.styleSheet().lower()
    square = gw.grid.visible_squares()[0]
    assert PALETTES["high_contrast"].panel.lower() in square.styleSheet().lower()



# --- simple, friendly head movement page -------------------------------------------------------

def page_widgets(window, kind):
    return window._pages["gaze"].findChildren(kind)


def test_page_has_one_start_button_and_no_clutter(window):
    from PySide6.QtWidgets import QSlider

    texts = "\n".join(visible_texts(window._pages["gaze"]))
    assert "How should selection work" not in texts
    assert "Start calibration" not in texts and "Use head movement control" not in texts
    assert not page_widgets(window, QSlider)  # speed is three plain choices, not a slider
    assert window.gaze_toggle.text() == "Start head control"


def test_start_button_starts_and_stops(window):
    window.gaze_toggle.click()
    assert window.prefs.gaze_control and window.gaze_window.gaze.enabled
    assert window.gaze_toggle.text() == "Stop head control"
    window.gaze_toggle.click()
    assert not window.prefs.gaze_control and not window.gaze_window.gaze.enabled
    assert window.gaze_toggle.text() == "Start head control"


def test_speed_choices_set_hold_time(window):
    window.gaze_toggle.click()
    ctrl = window.gaze_window.gaze.controller
    window._dwell_buttons["relaxed"].click()
    assert window.prefs.gaze_dwell_ms == 1600 and ctrl.dwell_ms == 1600
    assert window._dwell_buttons["relaxed"].isChecked() and not window._dwell_buttons["quick"].isChecked()
    window._dwell_buttons["quick"].click()
    assert window.prefs.gaze_dwell_ms == 800 and ctrl.dwell_ms == 800


def test_demo_items_hidden_only_on_hands_free_pages(window):
    window._navigate("gaze")
    assert not window._demo_shortcut.isVisible()
    window._navigate("overview")
    assert window._demo_shortcut.isVisible()


def test_problem_returns_to_head_page_with_message(window):
    window._navigate("overview")
    window.gaze_toggle.click()
    gw = window.gaze_window
    gw.problem.emit("Calibration was cancelled, so head movement control is off.")
    assert not window.prefs.gaze_control and not gw.isVisible()
    assert window.stack.currentWidget() is window._pages["gaze"]
    assert window.gaze_notice.isVisibleTo(window) and "cancelled" in window.gaze_notice.text()
    window.gaze_toggle.click()  # starting again clears the message
    assert not window.gaze_notice.isVisibleTo(window)


def wait(qapp, ms):
    import time

    end = time.monotonic() + ms / 1000
    while time.monotonic() < end:
        qapp.processEvents()
        time.sleep(0.01)


def test_exit_from_full_screen_leaves_full_screen_before_hiding(window, qapp):
    window.gaze_toggle.click()
    gw = window.gaze_window
    gw.showFullScreen()  # e.g. macOS green button
    qapp.processEvents()
    gw.portal.booking_finished.emit("close")  # Close on the booked popup
    assert not gw.isFullScreen()  # left full screen first...
    wait(qapp, 1200)
    assert not gw.isVisible()  # ...then hidden, so no empty full-screen space is left


def test_exit_brings_control_center_to_front(window, monkeypatch):
    raised = []
    monkeypatch.setattr(window, "raise_", lambda: raised.append(1))
    window.gaze_toggle.click()
    window.gaze_window.portal.booking_finished.emit("close")  # Close on the booked popup
    assert raised


# --- end of a booking ---------------------------------------------------------------------------

def test_quit_button_leaves_hands_free_without_booking(window):
    window.gaze_toggle.click()
    gw = window.gaze_window
    assert gw.btn_quit.isVisible() and gw.btn_quit.parentWidget() is gw.bar
    gw.btn_quit.click()  # mid-booking: no appointment needed to get out
    assert not window.prefs.gaze_control and not gw.gaze.enabled and not gw.isVisible()


def test_booking_popup_close_leaves_hands_free(window):
    window.gaze_toggle.click()
    window.gaze_window.portal.booking_finished.emit("close")
    assert not window.prefs.gaze_control and not window.gaze_window.isVisible()


def test_booking_popup_start_over_goes_back_to_step_one_without_calibrating(window, monkeypatch):
    from accessshift.ui.gaze_booking_window import GazeBookingWindow

    calibrations = []
    monkeypatch.setattr(GazeBookingWindow, "recalibrate", lambda self: calibrations.append(1))
    window.gaze_toggle.click()
    gw = window.gaze_window
    for choice in ("Myself", "Check-up", "Tomorrow 10:00"):
        next(b for b in gw.grid.visible_squares() if b.text() == choice).click()
    gw.portal._reset_flow()
    gw.portal.booking_finished.emit("start_over")
    assert window.prefs.gaze_control and gw.gaze.enabled and calibrations == []
    assert [b.text() for b in gw.grid.visible_squares()] == ["Myself", "Someone I care for"]
