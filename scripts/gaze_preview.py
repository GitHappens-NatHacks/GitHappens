"""Live webcam check for GazeControl: shows the camera, eye feature, EAR and blinks.

Run from the repo root:  python scripts/gaze_preview.py
Look at the centre of the screen and press C to centre the dot. Q or Esc quits.
The dot is a rough preview only; real screen mapping comes from 9-point calibration.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import cv2

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from accessshift.modules.gaze import GazeTracker  # noqa: E402

GAIN = 4.0  # how far the dot moves per unit of eye movement (preview only)


def main() -> int:
    tracker = GazeTracker(int(os.getenv("GAZE_CAMERA_INDEX", "0")))
    if not tracker.open():
        print("Could not open the camera. On macOS: System Settings > Privacy & Security > "
              "Camera, allow your terminal / VS Code, then run again.")
        return 1

    blinks = 0
    origin = None
    try:
        while True:
            sample = tracker.read()
            if not sample or not sample.get("camera_ok"):
                print("Camera returned no frame.")
                break
            frame = sample["frame"]
            h, w = frame.shape[:2]

            if sample["face"]:
                u, v = sample["feature"]
                if sample["blink"]:
                    blinks += 1
                if origin is not None:
                    x = 0.5 + (u - origin[0]) * GAIN
                    y = 0.5 + (v - origin[1]) * GAIN * 2  # vertical eye movement is smaller
                    x, y = min(max(x, 0.0), 1.0), min(max(y, 0.0), 1.0)
                    cv2.circle(frame, (int(x * w), int(y * h)), 12, (0, 200, 255), -1)
                text = f"eye u {u:.3f} v {v:+.3f}   EAR {sample['ear']:.3f}   deliberate blinks {blinks}"
                color = (0, 255, 0)
            else:
                text, color = "No face found - look at the camera", (0, 0, 255)

            cv2.putText(frame, text, (16, 32), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
            hint = "C = centre dot   Q = quit" + ("" if origin else "   (press C to show the dot)")
            cv2.putText(frame, hint, (16, h - 20), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
            cv2.imshow("AccessShift gaze preview", frame)

            key = cv2.waitKey(1) & 0xFF
            if key in (ord("q"), 27):
                break
            if key == ord("c") and sample["face"]:
                origin = sample["feature"]
    finally:
        tracker.close()
        cv2.destroyAllWindows()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
