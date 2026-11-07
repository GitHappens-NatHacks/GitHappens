"""Webcam gaze tracking with MediaPipe Face Mesh."""

from __future__ import annotations

import time

import cv2
import mediapipe as mp
import numpy as np

from accessshift.modules.gaze.blink import BlinkDetector

LEFT_EYE = [33, 160, 158, 133, 153, 144]
RIGHT_EYE = [362, 385, 387, 263, 373, 380]
LEFT_IRIS = [468, 469, 470, 471, 472]
RIGHT_IRIS = [473, 474, 475, 476, 477]


class GazeTracker:
    def __init__(self, camera_index: int = 0):
        self.camera_index = camera_index
        self.cap = None
        self.blink = BlinkDetector()
        self._mesh = mp.solutions.face_mesh.FaceMesh(
            max_num_faces=1,
            refine_landmarks=True,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5,
        )
        self.calibrated = False
        self._origin = None

    def open(self) -> bool:
        self.cap = cv2.VideoCapture(self.camera_index)
        return bool(self.cap and self.cap.isOpened())

    def close(self) -> None:
        if self.cap is not None:
            self.cap.release()
            self.cap = None
        self._mesh.close()

    def calibrate(self) -> None:
        sample = self.read()
        if sample and sample.get("gaze"):
            self._origin = sample["gaze"]
            self.calibrated = True

    def _points(self, landmarks, indices, w, h):
        return [(landmarks[i].x * w, landmarks[i].y * h) for i in indices]

    def read(self) -> dict | None:
        if self.cap is None:
            return None
        ok, frame = self.cap.read()
        if not ok:
            return {"camera_ok": False}

        frame = cv2.flip(frame, 1)
        h, w = frame.shape[:2]
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        result = self._mesh.process(rgb)
        ts = int(time.time() * 1000)
        payload = {"camera_ok": True, "calibrated": self.calibrated, "ts": ts, "frame": frame}

        if not result.multi_face_landmarks:
            return payload

        lm = result.multi_face_landmarks[0].landmark
        left_eye = self._points(lm, LEFT_EYE, w, h)
        right_eye = self._points(lm, RIGHT_EYE, w, h)
        left_iris = self._points(lm, LEFT_IRIS, w, h)
        right_iris = self._points(lm, RIGHT_IRIS, w, h)

        iris = np.mean(left_iris + right_iris, axis=0)
        gaze_x = float(iris[0] / w)
        gaze_y = float(iris[1] / h)

        if self._origin is not None:
            gaze_x = float(np.clip(0.5 + (gaze_x - self._origin[0]), 0, 1))
            gaze_y = float(np.clip(0.5 + (gaze_y - self._origin[1]), 0, 1))

        ear, blink = self.blink.update(left_eye, right_eye)
        payload.update({"gaze": (gaze_x, gaze_y), "ear": ear, "blink": blink})
        return payload
