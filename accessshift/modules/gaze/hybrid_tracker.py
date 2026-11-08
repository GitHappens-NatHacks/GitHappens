"""MediaPipe + EyeTrax on one camera when both are available.

MediaPipe stays the source of truth for head pose, EAR, and blink timing.
EyeTrax supplies a richer eye `feature` when it sees a face; otherwise the
MediaPipe iris feature is used unchanged.
"""

from __future__ import annotations

import time

import cv2

from accessshift.modules.gaze.blink import BlinkDetector, eye_aspect_ratio
from accessshift.modules.gaze.eyetrax_tracker import (
    EYETRAX_AVAILABLE,
    features_to_eye_point,
)
from accessshift.modules.gaze.features import LEFT_EYE, RIGHT_EYE, gaze_feature, head_feature

try:
    import mediapipe as mp
except Exception:  # pragma: no cover
    mp = None

if EYETRAX_AVAILABLE:
    from eyetrax import GazeEstimator
else:  # pragma: no cover
    GazeEstimator = None  # type: ignore[misc, assignment]


class HybridGazeTracker:
    backend_name = "hybrid"

    def __init__(self, camera_index: int = 0):
        if mp is None:
            raise RuntimeError("mediapipe is required for hybrid tracking")
        if not EYETRAX_AVAILABLE:
            raise RuntimeError("eyetrax is required for hybrid tracking")
        self.camera_index = camera_index
        self.cap = None
        self.blink = BlinkDetector()
        self._mesh = mp.solutions.face_mesh.FaceMesh(
            max_num_faces=1,
            refine_landmarks=True,
            min_detection_confidence=0.6,
            min_tracking_confidence=0.6,
        )
        self._estimator = GazeEstimator()

    def open(self) -> bool:
        self.cap = cv2.VideoCapture(self.camera_index)
        return bool(self.cap and self.cap.isOpened())

    def close(self) -> None:
        if self.cap is not None:
            self.cap.release()
            self.cap = None
        self._mesh.close()
        close = getattr(self._estimator, "close", None)
        if callable(close):
            close()

    def read(self) -> dict | None:
        if self.cap is None:
            return None
        ok, frame = self.cap.read()
        ts_ms = int(time.monotonic() * 1000)
        if not ok:
            return {"camera_ok": False, "face": False, "ts_ms": ts_ms, "backend": self.backend_name}

        frame = cv2.flip(frame, 1)
        h, w = frame.shape[:2]
        payload = {
            "camera_ok": True,
            "face": False,
            "ts_ms": ts_ms,
            "frame": frame,
            "backend": self.backend_name,
        }

        result = self._mesh.process(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        if not result.multi_face_landmarks:
            return payload

        points = [(p.x * w, p.y * h) for p in result.multi_face_landmarks[0].landmark]
        ear = (
            eye_aspect_ratio([points[i] for i in LEFT_EYE])
            + eye_aspect_ratio([points[i] for i in RIGHT_EYE])
        ) / 2.0
        mp_eyes = gaze_feature(points)
        eye_feat = mp_eyes
        used = "mediapipe"

        try:
            features, _blink_flag = self._estimator.extract_features(frame)
        except Exception:
            features = None
        if features is not None:
            try:
                et_eyes = features_to_eye_point(features)
                # EyeTrax helps left/right. MediaPipe keeps up/down (iris travel is tiny).
                eye_feat = (et_eyes[0], mp_eyes[1])
                used = "eyetrax+mediapipe"
            except Exception:
                pass

        payload.update(
            {
                "face": True,
                "feature": eye_feat,
                "head": head_feature(points),
                "ear": ear,
                "blink": self.blink.update(ear, ts_ms),
                "backend": used,
            }
        )
        payload["closed_ms"] = self.blink.closed_ms(ts_ms)
        return payload
