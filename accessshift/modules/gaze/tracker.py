"""Webcam gaze tracking with MediaPipe Face Mesh.

read() returns raw eye-relative features; mapping them to screen pixels is done
by GazeCalibration (calibration.py), not here.
"""

from __future__ import annotations

import time

import cv2
import mediapipe as mp

from accessshift.modules.gaze.blink import BlinkDetector, eye_aspect_ratio
from accessshift.modules.gaze.features import LEFT_EYE, RIGHT_EYE, gaze_feature, head_feature


class GazeTracker:
    def __init__(self, camera_index: int = 0):
        self.camera_index = camera_index
        self.cap = None
        self.blink = BlinkDetector()
        self._mesh = mp.solutions.face_mesh.FaceMesh(
            max_num_faces=1,
            refine_landmarks=True,  # adds the iris landmarks 468-477
            min_detection_confidence=0.6,
            min_tracking_confidence=0.6,
        )

    def open(self) -> bool:
        self.cap = cv2.VideoCapture(self.camera_index)
        return bool(self.cap and self.cap.isOpened())

    def close(self) -> None:
        if self.cap is not None:
            self.cap.release()
            self.cap = None
        self._mesh.close()

    def read(self) -> dict | None:
        """One frame. Keys: camera_ok, face, ts_ms, frame; plus feature (eyes), head, ear, blink, closed_ms when face is True."""
        if self.cap is None:
            return None
        ok, frame = self.cap.read()
        ts_ms = int(time.monotonic() * 1000)
        if not ok:
            return {"camera_ok": False, "face": False, "ts_ms": ts_ms}

        frame = cv2.flip(frame, 1)
        h, w = frame.shape[:2]
        result = self._mesh.process(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        payload = {"camera_ok": True, "face": False, "ts_ms": ts_ms, "frame": frame}

        if not result.multi_face_landmarks:
            return payload

        points = [(p.x * w, p.y * h) for p in result.multi_face_landmarks[0].landmark]
        ear = (
            eye_aspect_ratio([points[i] for i in LEFT_EYE])
            + eye_aspect_ratio([points[i] for i in RIGHT_EYE])
        ) / 2.0
        payload.update(
            {
                "face": True,
                "feature": gaze_feature(points),
                "head": head_feature(points),
                "ear": ear,
                "blink": self.blink.update(ear, ts_ms),
            }
        )
        payload["closed_ms"] = self.blink.closed_ms(ts_ms)  # >0 while eyes are shut
        return payload
