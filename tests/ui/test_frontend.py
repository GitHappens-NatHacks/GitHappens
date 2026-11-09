"""The redesigned AccessShift front end: Home, introduction, dashboard, profile, feature tabs, Demo Lab."""

from pathlib import Path

import pytest
from PySide6.QtCore import QPointF
from PySide6.QtWidgets import QLabel, QPushButton

import accessshift.ui.control_center as control_center
from accessshift.ui import gaze_mode
from accessshift.ui.control_center_settings import AccessibilitySettings
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
    w._change_option("letter_spacing_px", 0)  # the app font is shared by every test
    w.close()


def texts(widget):
    return [w.text() for kind in (QLabel, QPushButton) for w in widget.findChildren(kind)]


# --- Branding, Home splash and navigation ------------------------------------------------------

def test_home_is_only_the_logo_and_tagline(window):
    home = window._pages["home"]
    assert window.stack.currentWidget() is home
    assert not window.top_nav.isVisible()
    assert [t for t in texts(home) if t] == ["Access Without Limits"]
    assert not window.home_logo.pixmap().isNull()


def test_home_moves_to_the_dashboard_after_about_two_seconds(window, qapp):
    import time

    assert control_center.SPLASH_MS == 2000
    end = time.monotonic() + 2.6
    while time.monotonic() < end and window.stack.currentWidget() is window._pages["home"]:
        qapp.processEvents()
        time.sleep(0.02)
    assert window.stack.currentWidget() is window._pages["overview"]
    assert window.top_nav.isVisible()


def test_younify_name_everywhere(window):
    window._open_demo_lab("start")
    every = texts(window) + texts(window.demo_lab) + [window.windowTitle(), window.demo_lab.windowTitle()]
    assert not [t for t in every if "AccessShift" in t]
    assert window.windowTitle() == "Younify"


def test_top_navigation_lists_features_in_order(window):
    layout = window.top_bar_layout
    tabs = [layout.itemAt(i).widget().text() for i in range(layout.count())
            if layout.itemAt(i).widget() is not None and layout.itemAt(i).widget().objectName() == "navTab"]
    assert tabs == ["Home", "Dashboard", "SteadyHand", "Head movement", "SmartInterface"]
    assert [key for key, *_ in control_center.FEATURES] == ["steady", "gaze", "interface"]
    assert list(window.feature_cards) == ["steady", "gaze", "interface"]
    window._open_demo_lab("start")
    assert list(window.demo_lab._rail_buttons) == ["start", "steady", "gaze", "interface"]


def test_dashboard_heading_is_younify_and_quick_comfort_is_plain(window):
    page_texts = texts(window._pages["overview"])
    assert "Younify" in page_texts and "Dashboard" not in page_texts
    assert any(t.startswith("Your profile:") for t in page_texts)
    for removed in ("Make every page easier to read.", "Changes apply to every"):
        assert not [t for t in page_texts if removed in t]
    for _key, _icon, _title, description in control_center.FEATURES:  # no captions on the tool cards
        assert description not in page_texts
    assert not window.feature_cards["gaze"].meta.isVisibleTo(window.feature_cards["gaze"])


def test_profile_is_in_the_top_right_corner(window):
    window._navigate("overview")
    layout = window.top_bar_layout
    assert layout.itemAt(layout.count() - 1).widget() is window.profile_button
    assert "personalize" not in window._nav
    window.profile_button.click()
    assert window.stack.currentWidget() is window._pages["personalize"]


# --- Removed sections ---------------------------------------------------------------------------

@pytest.mark.parametrize("removed", [
    "LOCAL DEMO", "Local demo", "PRIVATE BY DESIGN", "Private by design", "DEMO ENVIRONMENT", "Demo environment",
    "SELECTED FEATURES", "Selected features", "Prototype status", "Communication", "Demo Lab & tests",
    "Live healthcare preview", "Live preview",
])
def test_removed_sections_are_gone(window, removed):
    assert not [t for t in texts(window) if removed in t]


def test_no_communication_or_test_lab_pages(window):
    assert "speech" not in window._pages and "test" not in window._pages


# --- Feature tabs hold their own demos ----------------------------------------------------------

def test_each_feature_tab_has_its_demo(window):
    from accessshift.ui.steadyhand_panel import SteadyHandTrialPanel

    assert window._pages["steady"].findChildren(SteadyHandTrialPanel)
    assert any("SmartInterface demo" in t for t in texts(window._pages["interface"]))
    assert window.gaze_toggle.text() == "Start head control"


def test_head_movement_points_with_the_head_only(window):
    assert not [t for t in texts(window._pages["gaze"]) if "My eyes" in t]
    window.gaze_toggle.click()
    gw = window.gaze_window
    assert gw.gaze.enabled and gw.gaze.controller.source == "head"
    assert not gw.btn_source.isVisible() and gw.gaze.allow_eyes is False
    window.gaze_toggle.click()
    assert not gw.gaze.enabled


def test_word_highlighting_is_removed(window):
    assert not [t for t in texts(window) if "highlight" in t.lower()]
    assert not hasattr(window.prefs, "word_highlight")


def test_hands_free_window_has_a_quit_button(window):
    window.gaze_toggle.click()
    window.gaze_window.btn_quit.click()
    assert not window.prefs.gaze_control and not window.gaze_window.isVisible()


# --- SmartInterface settings apply everywhere ---------------------------------------------------

def test_letter_spacing_applies_across_pages_and_windows(window, qapp):
    window._change_option("letter_spacing_px", 3)
    window._open_demo_lab("start")
    qapp.processEvents()
    dashboard_title = next(l for l in window._pages["overview"].findChildren(QLabel) if l.objectName() == "bannerTitle")
    lab_title = next(l for l in window.demo_lab.findChildren(QLabel) if l.objectName() == "bannerTitle")
    assert dashboard_title.font().letterSpacing() == 3
    assert lab_title.font().letterSpacing() == 3


def test_text_size_applies_to_every_page(window, qapp):
    def title_size():
        qapp.processEvents()
        title = next(l for l in window._pages["steady"].findChildren(QLabel) if l.objectName() == "bannerTitle")
        return title.fontInfo().pixelSize()

    before = title_size()
    window._change_option("font_size_pct", 150)
    assert title_size() > before


def test_choosing_a_tint_colour_turns_the_tint_on(window):
    assert not window.tint_manager.active
    window._tint_buttons["cool"].click()
    assert window.tint_manager.active and window.prefs.tint_color == "cool"
    assert window._tint_buttons["cool"].isChecked()
    window.tint_switch.click()
    assert not window.tint_manager.active


# --- Demo Lab ---------------------------------------------------------------------------------

def test_demo_lab_opens_with_every_feature(window):
    window._demo_shortcut.click()
    lab = window.demo_lab
    assert lab.isVisible()
    assert set(lab._rail_buttons) == {"start", "interface", "steady", "gaze"}
    for key in ("interface", "steady", "gaze"):
        lab.show_section(key)
        assert lab.stack.currentWidget() is lab._pages[key]


def test_demo_form_follows_the_profile(window):
    window._change_module("smart_interface", True)
    window._open_demo_lab("interface")
    form = window.demo_lab.healthcare
    assert form._accessible and form.step_label.text() == "Step 1 of 2"
    form.view_toggle.click()  # View original form
    assert not form._accessible and form.primary.text() == "Try simplified"
    window._change_option("font_size_pct", 140)
    assert not form._accessible  # a text size change never undoes the manual switch
    form.primary.click()
    assert form._accessible
    window._change_module("smart_interface", False)
    assert not form._accessible and window.demo_lab.smart_off_notice.isVisibleTo(window.demo_lab)


def test_demo_form_steps_finish_and_start_again(qapp):
    from accessshift.ui.healthcare_demo_window import HealthcareDemoWindow

    form = HealthcareDemoWindow(ROOT, smart_interface_enabled=True)
    form.show()
    sent = []
    form.demo_submitted.connect(sent.append)
    form.name.setText("Alex Morgan")
    assert form.primary.text() == "Continue" and not form.back.isVisible()
    form.primary.click()
    assert form.step_label.text() == "Step 2 of 2" and form.back.isVisible()
    assert form.department.isVisible() and not form.name.isVisible()
    assert form.primary.text() == "Finish demo"
    form.back.click()
    assert form.name.isVisible() and form.name.text() == "Alex Morgan"  # nothing typed is lost
    form.primary.click()
    form.department.setCurrentIndex(1)
    form.primary.click()
    assert form.done_view.isVisible() and form.primary.text() == "Start again"
    assert sent and sent[0]["full_name"] == "Alex Morgan" and sent[0]["department"] == "Neurology"
    form.primary.click()
    assert form.name.text() == "" and form.step_label.text() == "Step 1 of 2"
    form.view_toggle.click()
    assert all(field.isVisible() for _l, field in form.fields)  # original: all details at once
    form.close()


def test_demo_lab_starts_the_head_movement_demo(window):
    window._open_demo_lab("gaze")
    lab = window.demo_lab
    assert not hasattr(lab, "eye_button")
    lab.head_button.click()
    assert window.gaze_window.gaze.enabled and window.gaze_window.gaze.controller.source == "head"
    assert lab.head_button.text() == "Stop the demo"
    lab.head_button.click()
    assert not window.gaze_window.gaze.enabled


def test_turning_steadyhand_off_sets_strength_to_zero(window):
    window._change_module("steady_hand", True)
    window._change_option("tremor_strength", 120)
    window.steady_toggle.switch.click()  # Use SteadyHand: off
    assert not window.prefs.steady_hand and window.prefs.tremor_strength == 0
    assert window.strength_slider.value() == 0 and window.steady.strength == 0
    window.steady_toggle.switch.click()  # back on: the previous strength returns
    assert window.prefs.steady_hand and window.prefs.tremor_strength == 120
    assert window.strength_slider.value() == 120
