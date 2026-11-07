from PySide6.QtCore import QCoreApplication, QPoint, QRect, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QPushButton

from accessshift.modules.gaze.controller import GazeController, widget_under
from accessshift.ui.gaze_calibration_dialog import GazeCalibrationDialog
from accessshift.ui.gaze_keyboard import GazeKeyboard
from accessshift.ui.gaze_overlay import GazeOverlay

SCREEN = QRect(0, 0, 1000, 800)


def fake_sample(t, norm):
    x, y = norm
    return {"camera_ok": True, "face": True, "ts_ms": t, "feature": (0.4 + 0.2 * x, 0.04 * y),
            "ear": 0.3, "blink": False}


# --- calibration dialog ------------------------------------------------------------

def test_calibration_dialog_fits_and_unpauses(qapp):
    ctrl = GazeController(hit_test=lambda p: None, screen_rect=SCREEN)
    dlg = GazeCalibrationDialog(ctrl, screen_rect=SCREEN, result_delay_ms=0)
    dlg.begin()
    assert ctrl.paused
    t = 0
    while dlg.isVisible() and t < 60_000:
        ctrl.process(fake_sample(t, dlg.current_target_norm()))
        t += 33
    assert dlg.result() == GazeCalibrationDialog.DialogCode.Accepted
    assert ctrl.calibration.is_fitted and not ctrl.paused
    assert ctrl.error_px < 5
    assert t < 25_000  # 13 dots x 1.5 s, no retries for steady eyes


def test_calibration_dialog_escape_cancels(qapp):
    ctrl = GazeController(hit_test=lambda p: None, screen_rect=SCREEN)
    dlg = GazeCalibrationDialog(ctrl, screen_rect=SCREEN)
    dlg.begin()
    QTest.keyClick(dlg, Qt.Key_Escape)
    assert not ctrl.paused and not ctrl.calibration.is_fitted
    assert dlg.result() == GazeCalibrationDialog.DialogCode.Rejected


# --- overlay -------------------------------------------------------------------------

def test_overlay_is_ignored_by_hit_test(qapp):
    button = QPushButton("Book")
    button.setGeometry(100, 100, 200, 100)
    button.show()
    overlay = GazeOverlay(SCREEN)
    overlay.show()
    overlay.raise_()
    QCoreApplication.processEvents()
    assert widget_under(QPoint(150, 150)) is button
    overlay.set_point(QPoint(150, 150))
    overlay.set_dwell(0.5)  # paints without error
    overlay.set_target(QRect(100, 100, 200, 100))
    overlay.repaint()
    overlay.close()
    button.close()


# --- keyboard ------------------------------------------------------------------------

class FakeSpeech:
    def __init__(self):
        self.spoken = []

    def speak_async(self, text):
        self.spoken.append(text)


def test_suggestion_replaces_word(qapp):
    kb = GazeKeyboard(FakeSpeech())
    kb.set_text("book app")
    assert kb.suggestion_buttons[0].text() == "appointment"
    kb.suggestion_buttons[0].click()
    assert kb.text() == "book appointment "


def test_typing_backspace_clear(qapp):
    kb = GazeKeyboard(FakeSpeech())
    kb.key_buttons["H"].click()
    kb.key_buttons["I"].click()
    assert kb.text() == "hi"
    kb.key_buttons["⌫"].click()
    assert kb.text() == "h"
    kb.key_buttons["Space"].click()
    assert kb.text() == "h "
    kb.key_buttons["Clear"].click()
    assert kb.text() == ""


def test_keys_meet_min_target_size(qapp):
    kb = GazeKeyboard(FakeSpeech(), error_px=60)  # min_target_px(60) == 120
    buttons = list(kb.key_buttons.values()) + kb.suggestion_buttons
    assert buttons and all(b.minimumWidth() >= 120 and b.minimumHeight() >= 120 for b in buttons)


def test_speak_uses_non_blocking_speech(qapp):
    speech = FakeSpeech()
    kb = GazeKeyboard(speech)
    kb.set_text("help ")
    kb.key_buttons["Speak"].click()
    assert speech.spoken == ["help"]


def test_speak_empty_does_nothing(qapp):
    speech = FakeSpeech()
    kb = GazeKeyboard(speech)
    kb.key_buttons["Speak"].click()
    assert speech.spoken == []
