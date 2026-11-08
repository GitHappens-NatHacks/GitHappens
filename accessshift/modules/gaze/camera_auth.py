"""macOS camera authorization helpers for OpenCV.

OpenCV cannot show the system camera permission dialog from a worker thread.
Authorize on the Qt main thread first. Then allow later opens to skip that prompt.
"""

from __future__ import annotations

import os
import time


def prepare_camera_for_worker(camera_index: int = 0) -> tuple[bool, str]:
    """Open the camera once on the calling thread then arm worker-safe capture.

    Returns (ok, message). Call this from the UI thread before GazeWorker starts.
    """
    import cv2

    # Allow this main-thread open to request macOS Camera permission.
    os.environ.pop("OPENCV_AVFOUNDATION_SKIP_AUTH", None)

    cap = cv2.VideoCapture(camera_index)
    if not cap.isOpened():
        # First launch often shows the permission sheet. Wait briefly then retry.
        time.sleep(1.5)
        cap.release()
        cap = cv2.VideoCapture(camera_index)

    if not cap.isOpened():
        os.environ["OPENCV_AVFOUNDATION_SKIP_AUTH"] = "1"
        return (
            False,
            "Camera could not be opened. On macOS allow camera access in "
            "System Settings > Privacy & Security > Camera for this app (Terminal or VS Code). "
            "Then choose Start head control again.",
        )

    ok, _frame = cap.read()
    cap.release()

    # Later opens from GazeWorker happen off the UI thread.
    os.environ["OPENCV_AVFOUNDATION_SKIP_AUTH"] = "1"

    if not ok:
        return (
            False,
            "Camera opened but returned no frames. Quit other apps using the webcam and try again.",
        )
    return True, "Camera authorized on the main thread."
