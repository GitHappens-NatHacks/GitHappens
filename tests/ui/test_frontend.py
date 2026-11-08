"""The redesigned AccessShift front end: Home, introduction, dashboard, profile, feature tabs, Demo Lab."""

from pathlib import Path

import pytest
from PySide6.QtCore import QPointF
from PySide6.QtWidgets import QLabel, QPushButton

import accessshift.ui.control_center as control_center
from accessshift.ui import gaze_mode
from accessshift.ui.control_center_settings import AccessibilitySettings
from accessshift.ui.main_window import MainWindow
from accessshift.ui.word_highlight import word_rect
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


# --- Home and introduction ---------------------------------------------------------------------

def test_app_opens_on_the_home_page_not_the_dashboard(window):
    assert window.stack.currentWidget() is window._pages["home"]
    assert not window.sidebar.isVisible()


def test_explore_opens_the_introduction_then_the_dashboard(window):
    window._explore_button.click()
    assert window.stack.currentWidget() is window._pages["intro"]
    for _ in range(len(control_center.INTRO_SLIDES)):
        window.intro_next.click()
    assert window.intro_actions.isVisible()
    window._navigate("overview")
    assert window.stack.currentWidget() is window._pages["overview"] and window.sidebar.isVisible()


def test_profile_is_in_the_top_right_corner(window):
    assert window.home_profile_button.text() == "My accessibility profile"
    window._navigate("overview")
    layout = window.top_bar_layout
    assert layout.itemAt(layout.count() - 1).widget() is window.profile_button
    assert "personalize" not in window._nav  # no longer in the sidebar
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
    assert window.eye_toggle.text() == "Start eye control"


def test_eye_tab_starts_hands_free_with_the_eyes(window):
    window.eye_toggle.click()
    gw = window.gaze_window
    assert gw.gaze.enabled and gw.gaze.controller.source == "eyes"
    assert window.eye_toggle.text() == "Stop eye control"
    assert window.gaze_toggle.text() == "Start head control"
    window.eye_toggle.click()
    assert not gw.gaze.enabled


# --- SmartInterface settings apply everywhere ---------------------------------------------------

def test_letter_spacing_applies_across_pages_and_windows(window, qapp):
    window._change_option("letter_spacing_px", 3)
    window._open_demo_lab("start")
    qapp.processEvents()
    dashboard_title = next(l for l in window._pages["overview"].findChildren(QLabel) if l.objectName() == "pageTitle")
    lab_title = next(l for l in window.demo_lab.findChildren(QLabel) if l.objectName() == "pageTitle")
    assert dashboard_title.font().letterSpacing() == 3
    assert lab_title.font().letterSpacing() == 3


def test_text_size_applies_to_every_page(window, qapp):
    def title_size():
        qapp.processEvents()
        title = next(l for l in window._pages["steady"].findChildren(QLabel) if l.objectName() == "pageTitle")
        return title.fontInfo().pixelSize()

    before = title_size()
    window._change_option("font_size_pct", 150)
    assert title_size() > before


def test_word_highlighting_is_an_on_off_option(window):
    assert not window.highlighter.enabled
    window.highlight_row.switch.click()
    assert window.prefs.word_highlight and window.highlighter.enabled
    window.highlight_row.switch.click()
    assert not window.highlighter.enabled


def test_word_rect_finds_the_word_under_a_point(qapp):
    lbl = QLabel("Book your appointment")
    lbl.resize(400, 40)
    lbl.show()
    qapp.processEvents()
    rect = word_rect(lbl, QPointF(5, 20))
    assert rect is not None and rect.width() > 10
    assert word_rect(lbl, QPointF(395, 20)) is None  # past the end of the text


def test_choosing_a_tint_colour_turns_the_tint_on(window):
    assert not window.tint_manager.active
    window._tint_buttons["cool"].click()
    assert window.tint_manager.active and window.prefs.tint_color == "cool"
    assert window._tint_buttons["cool"].isChecked()
    window.tint_switch.click()
    assert not window.tint_manager.active


# --- Demo Lab ---------------------------------------------------------------------------------

def test_demo_lab_opens_with_all_four_features(window):
    window._demo_shortcut.click()
    lab = window.demo_lab
    assert lab.isVisible()
    assert set(lab._rail_buttons) == {"start", "interface", "steady", "gaze", "eyes"}
    for key in ("interface", "steady", "gaze", "eyes"):
        lab.show_section(key)
        assert lab.stack.currentWidget() is lab._pages[key]


def test_demo_lab_form_follows_the_profile_and_compares_with_original(window):
    window._change_module("smart_interface", True)
    window._open_demo_lab("interface")
    form = window.demo_lab.healthcare
    assert form._accessible  # reflects the profile straight away
    window.demo_lab.compare_original.click()
    assert not form._accessible
    window._change_option("font_size_pct", 140)
    assert not form._accessible  # stays on the original while comparing
    window.demo_lab.compare_adapted.click()
    assert form._accessible and form._visual_settings["font_size_pct"] == 140
    window._change_module("smart_interface", False)
    assert not form._accessible and window.demo_lab.smart_off_notice.isVisibleTo(window.demo_lab)


def test_demo_lab_starts_head_and_eye_demos(window):
    window._open_demo_lab("gaze")
    lab = window.demo_lab
    lab.head_button.click()
    assert window.gaze_window.gaze.enabled and window.gaze_window.gaze.controller.source == "head"
    assert lab.head_button.text().startswith("Stop")
    lab.eye_button.click()  # switches the running session to the eyes
    assert window.gaze_window.gaze.controller.source == "eyes"
    lab.eye_button.click()
    assert not window.gaze_window.gaze.enabled
