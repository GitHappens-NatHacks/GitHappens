"""Live webcam check for GazeControl: shows the camera, gaze point, EAR and blinks.

Run from the repo root:  python scripts/gaze_preview.py
Press C to centre (calibrate) on where you are looking, Q or Esc to quit.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import cv2

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from accessshift.modules.gaze import GazeTracker  # noqa: E402


def main() -> int:
    tracker = GazeTracker(int(os.getenv("GAZE_CAMERA_INDEX", "0")))
    if not tracker.open():
        print("Could not open the camera. On macOS: System Settings > Privacy & Security > "
              "Camera, allow your terminal / VS Code, then run again.")
        return 1

    blinks = 0
    try:
        while True:
            sample = tracker.read()
            if not sample or not sample.get("camera_ok"):
                print("Camera returned no frame.")
                break
            frame = sample["frame"]
            h, w = frame.shape[:2]

            if "gaze" in sample:
                gx, gy = sample["gaze"]
                cv2.circle(frame, (int(gx * w), int(gy * h)), 12, (0, 200, 255), -1)
                if sample["blink"]:
                    blinks += 1
                text = f"EAR {sample['ear']:.3f}   blinks {blinks}   calibrated {sample['calibrated']}"
                color = (0, 255, 0)
            else:
                text, color = "No face found - look at the camera", (0, 0, 255)

            cv2.putText(frame, text, (16, 32), cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)
            cv2.putText(frame, "C = centre   Q = quit", (16, h - 20),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
            cv2.imshow("AccessShift gaze preview", frame)

            key = cv2.waitKey(1) & 0xFF
            if key in (ord("q"), 27):
                break
            if key == ord("c"):
                tracker.calibrate()
    finally:
        tracker.close()
        cv2.destroyAllWindows()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
