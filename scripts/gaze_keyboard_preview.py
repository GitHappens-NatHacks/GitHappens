"""Try the Task 6 gaze screens with your webcam, outside the main app.

Run from the repo root:  python scripts/gaze_keyboard_preview.py
1. Full-screen calibration (follow the dots; Esc cancels).
2. Gaze cursor + eye-typing keyboard: look at a key to dwell-click it, or slow-blink.
   Type a word, pick a suggestion, look at Speak. Close the keyboard window to quit.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtWidgets import QApplication, QLabel, QVBoxLayout, QWidget  # noqa: E402

from accessshift.modules.gaze.controller import GazeController  # noqa: E402
from accessshift.modules.speech.tts import SpeechEngine  # noqa: E402
from accessshift.ui.gaze_calibration_dialog import GazeCalibrationDialog  # noqa: E402
from accessshift.ui.gaze_keyboard import GazeKeyboard  # noqa: E402
from accessshift.ui.gaze_overlay import GazeOverlay  # noqa: E402


def main() -> int:
    app = QApplication(sys.argv)
    ctrl = GazeController()
    ctrl.start(int(os.getenv("GAZE_CAMERA_INDEX", "0")))

    if not GazeCalibrationDialog(ctrl).run():
        ctrl.stop()
        return 0

    window = QWidget()
    window.setWindowTitle(f"Gaze keyboard preview (accuracy ±{ctrl.error_px:.0f} px, dwell {ctrl.dwell_ms} ms)")
    layout = QVBoxLayout(window)
    status = QLabel("Gaze tracking")
    ctrl.status.connect(status.setText)
    layout.addWidget(status)
    layout.addWidget(GazeKeyboard(SpeechEngine(), error_px=ctrl.error_px))
    window.showMaximized()

    overlay = GazeOverlay()
    ctrl.point.connect(overlay.set_point)
    ctrl.dwell.connect(overlay.set_dwell)
    overlay.show()

    app.lastWindowClosed.connect(app.quit)
    code = app.exec()
    ctrl.stop()
    return code


if __name__ == "__main__":
    raise SystemExit(main())
