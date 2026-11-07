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


HEAD_POSES_FEATURES = {
    "center": (0.0, 0.60),
    "left": (-0.20, 0.60),
    "right": (0.20, 0.60),
    "up": (0.0, 0.45),
    "down": (0.0, 0.75),
}


def run_head_dialog(ctrl, poses, max_ms=30_000):
    dlg = GazeCalibrationDialog.for_controller(ctrl, screen_rect=SCREEN, result_delay_ms=0)
    dlg.begin()
    t, seen = 0, []
    while dlg.isVisible() and t < max_ms:
        step = dlg.current_step()
        if not seen or seen[-1] != step:
            seen.append(step)
        ctrl.process(fake_sample(t, (0.5, 0.5)) | {"head": poses[step]})
        t += 33
    return dlg, seen, t


def test_head_calibration_guides_center_left_right_up_down(qapp):
    ctrl = GazeController(hit_test=lambda p: None, screen_rect=SCREEN)
    dlg, seen, t = run_head_dialog(ctrl, HEAD_POSES_FEATURES)
    assert seen == ["center", "left", "right", "up", "down"]
    assert dlg.result() == GazeCalibrationDialog.DialogCode.Accepted
    up_y = ctrl.calibration.map(HEAD_POSES_FEATURES["up"])[1]
    right_x = ctrl.calibration.map(HEAD_POSES_FEATURES["right"])[0]
    assert up_y < SCREEN.height() / 2 and right_x > SCREEN.width() / 2  # up is up, right is right
    assert t < 12_000


def test_head_calibration_prompts_name_each_direction(qapp):
    from accessshift.ui.gaze_calibration_dialog import HEAD_STEP_TEXT

    assert "LEFT" in HEAD_STEP_TEXT["left"] and "UP" in HEAD_STEP_TEXT["up"]
    ctrl = GazeController(hit_test=lambda p: None, screen_rect=SCREEN)
    dlg = GazeCalibrationDialog.for_controller(ctrl, screen_rect=SCREEN)
    assert "head" in dlg.instruction.lower()


def test_head_calibration_retries_when_user_barely_moves(qapp):
    ctrl = GazeController(hit_test=lambda p: None, screen_rect=SCREEN)
    tiny = dict(HEAD_POSES_FEATURES, up=(0.0, 0.598), down=(0.0, 0.602))
    dlg, seen, _ = run_head_dialog(ctrl, tiny, max_ms=12_000)
    assert dlg.isVisible() and not ctrl.calibration.is_fitted
    assert seen[:6] == ["center", "left", "right", "up", "down", "center"]  # started again
    assert "tilt" in dlg.message().lower()
    dlg.reject()


def test_eyes_calibration_keeps_nine_dots_and_check(qapp):
    ctrl = GazeController(hit_test=lambda p: None, screen_rect=SCREEN)
    ctrl.set_source("eyes")
    dlg = GazeCalibrationDialog.for_controller(ctrl, screen_rect=SCREEN, result_delay_ms=0)
    assert "look" in dlg.instruction.lower()
    dlg.begin()
    assert len(dlg.current_points()) == 9
    dlg.reject()


def test_head_calibration_ignores_eye_openness_when_tilting(qapp):
    # Tilting the head up/down makes the eyelids look narrower to the webcam.
    ctrl = GazeController(hit_test=lambda p: None, screen_rect=SCREEN)
    dlg = GazeCalibrationDialog.for_controller(ctrl, screen_rect=SCREEN, result_delay_ms=0)
    dlg.begin()
    t = 0
    while dlg.isVisible() and t < 20_000:
        step = dlg.current_step()
        ear = 0.15 if step in ("up", "down") else 0.3
        ctrl.process(fake_sample(t, (0.5, 0.5)) | {"head": HEAD_POSES_FEATURES[step], "ear": ear})
        t += 33
    assert dlg.result() == GazeCalibrationDialog.DialogCode.Accepted
    assert t < 12_000  # no endless retries on the up/down steps


def no_face(ctrl, t0, t1):
    for t in range(t0, t1, 33):
        ctrl.process({"camera_ok": True, "face": False, "ts_ms": t})


def test_head_calibration_shows_face_not_found_after_a_second(qapp):
    from accessshift.ui.gaze_calibration_dialog import NO_FACE

    ctrl = GazeController(hit_test=lambda p: None, screen_rect=SCREEN)
    dlg = GazeCalibrationDialog.for_controller(ctrl, screen_rect=SCREEN)
    dlg.begin()
    assert dlg.current_step() == "center"
    no_face(ctrl, 0, 500)
    assert dlg.problem() == ""  # a brief loss is not an error
    no_face(ctrl, 500, 1300)
    assert dlg.problem() == NO_FACE
    ctrl.process(fake_sample(1400, (0.5, 0.5)) | {"head": (0.0, 0.6)})
    assert dlg.problem() == ""
    dlg.reject()


def test_turned_head_losing_the_face_gets_a_gentle_hint_not_an_error(qapp):
    from accessshift.ui.gaze_calibration_dialog import NO_FACE, TURN_BACK

    ctrl = GazeController(hit_test=lambda p: None, screen_rect=SCREEN)
    dlg = GazeCalibrationDialog.for_controller(ctrl, screen_rect=SCREEN)
    dlg.begin()
    t = 0
    while dlg.current_step() == "center":
        ctrl.process(fake_sample(t, (0.5, 0.5)) | {"head": HEAD_POSES_FEATURES["center"]})
        t += 33
    assert dlg.current_step() == "left"
    no_face(ctrl, t, t + 1500)  # turned so far the camera lost the face
    assert dlg.problem() == TURN_BACK and dlg.problem() != NO_FACE
    assert "little" in dlg.current_instruction().lower()
    dlg.reject()


def test_calibration_says_when_camera_sends_nothing(qapp):
    ctrl = GazeController(hit_test=lambda p: None, screen_rect=SCREEN)
    dlg = GazeCalibrationDialog.for_controller(ctrl, screen_rect=SCREEN)
    dlg.begin()
    dlg.check_camera(now_ms=dlg.started_ms() + 3000)  # 3 s with no samples at all
    assert "camera" in dlg.problem().lower()
    dlg.reject()


def test_head_calibration_tunes_closed_eyes_to_the_narrowest_pose(qapp):
    ctrl = GazeController(hit_test=lambda p: None, screen_rect=SCREEN)
    dlg = GazeCalibrationDialog.for_controller(ctrl, screen_rect=SCREEN, result_delay_ms=0)
    dlg.begin()
    t = 0
    while dlg.isVisible() and t < 20_000:
        step = dlg.current_step()
        ear = 0.18 if step == "down" else 0.3
        ctrl.process(fake_sample(t, (0.5, 0.5)) | {"head": HEAD_POSES_FEATURES[step], "ear": ear})
        t += 33
    assert ctrl.last_blink_ears == [0.18]  # threshold = 0.75 x the tilted-down eye openness
