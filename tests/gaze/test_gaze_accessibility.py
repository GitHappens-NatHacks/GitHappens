import time

import numpy as np
from PySide6.QtCore import QCoreApplication, QRect
from PySide6.QtWidgets import QLabel, QPushButton, QVBoxLayout, QWidget

from accessshift.modules.gaze.controller import GazeController, STATUS_NO_FACE, STATUS_TRACKING
from accessshift.ui import gaze_style
from accessshift.ui.gaze_camera_preview import GazeCameraPreview
from accessshift.ui.gaze_mode import GazeMode
from accessshift.ui.gaze_overlay import GazeOverlay


def contrast_ratio(fg: str, bg: str) -> float:
    def lum(hex_color):
        rgb = [int(hex_color[i:i + 2], 16) / 255 for i in (1, 3, 5)]
        lin = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in rgb]
        return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]

    hi, lo = sorted((lum(fg), lum(bg)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def make_window():
    w = QWidget()
    w.setStyleSheet("QLabel { color: grey; }")
    layout = QVBoxLayout(w)
    styled = QPushButton("Myself")
    styled.setMinimumHeight(64)
    styled.setStyleSheet("QPushButton { background:#e7f6f1; font-size:18px; }")
    plain = QPushButton("Back")
    layout.addWidget(styled)
    layout.addWidget(plain)
    layout.addWidget(QLabel("Pick a time"))
    return w, styled, plain


# --- gaze style ------------------------------------------------------------------------

def test_gaze_colors_meet_wcag_aaa():
    assert contrast_ratio(gaze_style.TEXT, gaze_style.BUTTON_BG) >= 7
    assert contrast_ratio(gaze_style.TEXT, gaze_style.TARGET_BG) >= 7


def test_apply_enlarges_buttons_and_restore_is_exact(qapp):
    w, styled, plain = make_window()
    before = [(b.styleSheet(), b.minimumHeight()) for b in (styled, plain)]
    window_before = w.styleSheet()

    gaze_style.apply(w)
    for b in (styled, plain):
        assert b.minimumHeight() >= gaze_style.BUTTON_HEIGHT
        assert gaze_style.TEXT in b.styleSheet()
    assert gaze_style.is_applied(w)
    gaze_style.apply(w)  # applying twice must not lose the originals

    gaze_style.restore(w)
    assert [(b.styleSheet(), b.minimumHeight()) for b in (styled, plain)] == before
    assert w.styleSheet() == window_before and not gaze_style.is_applied(w)
    gaze_style.restore(w)  # restoring twice is harmless


def test_target_highlight_moves_between_buttons(qapp):
    w, styled, plain = make_window()
    gaze_style.apply(w)
    gaze_style.highlight(styled)
    assert styled.property("gazeTarget") is True
    gaze_style.highlight(plain)
    assert styled.property("gazeTarget") is False and plain.property("gazeTarget") is True
    gaze_style.highlight(None)
    assert plain.property("gazeTarget") is False
    gaze_style.restore(w)


# --- camera preview and alerts ------------------------------------------------------------

def test_camera_preview_shows_frame_target_and_errors(qapp):
    p = GazeCameraPreview()
    p.on_sample({"face": True, "frame": np.zeros((180, 320, 3), np.uint8), "ts_ms": 0})
    assert not p.frame_pixmap().isNull()
    p.set_target_name("Book appointment")
    p.set_dwell(0.5)
    assert "Book appointment" in p.target_text()
    p.show_error(STATUS_NO_FACE)
    assert p.error_text() == STATUS_NO_FACE
    p.show_error(None)
    assert p.error_text() == ""
    p.repaint()


def test_overlay_banner(qapp):
    o = GazeOverlay(QRect(0, 0, 800, 600))
    o.set_message("Face not found")
    assert o.message() == "Face not found"
    o.show()
    o.repaint()
    o.set_message(None)
    assert o.message() == ""
    o.close()


# --- gaze mode turns it all on and off -----------------------------------------------------

class FakeTracker:
    def open(self):
        return True

    def read(self):
        time.sleep(0.005)
        return {"camera_ok": True, "face": False, "ts_ms": int(time.monotonic() * 1000),
                "frame": np.zeros((480, 640, 3), np.uint8)}

    def close(self):
        pass


def test_gaze_mode_styles_window_and_reverts(qapp):
    w, styled, plain = make_window()
    gm = GazeMode(w, screen_rect=QRect(0, 0, 1000, 800), tracker_factory=FakeTracker, calibrate_on_start=False)
    gm.set_enabled(True)
    assert styled.minimumHeight() >= gaze_style.BUTTON_HEIGHT and gm.preview.isVisible()
    gm.set_enabled(False)
    assert styled.minimumHeight() == 64 and not gm.preview.isVisible()


def test_gaze_mode_alerts_follow_status(qapp):
    gm = GazeMode(screen_rect=QRect(0, 0, 1000, 800), calibrate_on_start=False)
    gm.controller.status.emit(STATUS_NO_FACE)
    assert gm.overlay.message() == STATUS_NO_FACE and gm.preview.error_text() == STATUS_NO_FACE
    gm.controller.status.emit(STATUS_TRACKING)
    assert gm.overlay.message() == "" and gm.preview.error_text() == ""


def test_preview_frames_are_downscaled(qapp):
    c = GazeController(hit_test=lambda p: None, screen_rect=QRect(0, 0, 1000, 800))
    frames = []
    c.raw_sample.connect(lambda s: frames.append(s.get("frame")))
    c.start(tracker_factory=FakeTracker, preview=True)
    end = time.monotonic() + 3
    while not frames and time.monotonic() < end:
        QCoreApplication.processEvents()
        time.sleep(0.01)
    c.stop()
    assert frames and frames[0] is not None and frames[0].shape[1] == 320


def test_portal_big_buttons_set_dark_text_on_light_background():
    # Without an explicit colour, macOS dark mode draws white text on the light button.
    from accessshift.ui.portal_view import PortalView

    css = PortalView._big_btn_css()
    assert "color:#0B1F1A" in css.replace(" ", "")
    assert contrast_ratio("#0B1F1A", "#E7F6F1") >= 7
