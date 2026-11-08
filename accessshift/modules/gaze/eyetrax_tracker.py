"""Optional EyeTrax webcam tracker.

Produces the same sample dict as GazeTracker. Falls back is handled by create_tracker().
EyeTrax uses MediaPipe Face Landmarker + richer normalized eye landmarks.
"""

from __future__ import annotations

import time

import cv2
import numpy as np

from accessshift.modules.gaze.blink import BlinkDetector

try:
    from eyetrax import GazeEstimator
    from eyetrax.constants import LEFT_EYE_INDICES, MUTUAL_INDICES, RIGHT_EYE_INDICES

    EYETRAX_AVAILABLE = True
except Exception:  # import or native deps
    EYETRAX_AVAILABLE = False
    GazeEstimator = None  # type: ignore[misc, assignment]


_SUBSET = (LEFT_EYE_INDICES + RIGHT_EYE_INDICES + MUTUAL_INDICES) if EYETRAX_AVAILABLE else []


def eyetrax_available() -> bool:
    return EYETRAX_AVAILABLE


def features_to_eye_point(features: np.ndarray) -> tuple[float, float]:
    """Compact 2D gaze feature from EyeTrax's normalized eye landmarks (iris mean)."""
    n = len(_SUBSET)
    coords = np.asarray(features[: n * 3], dtype=float).reshape(n, 3)
    left = coords[_SUBSET.index(468)]
    right = coords[_SUBSET.index(473)]
    return (float((left[0] + right[0]) / 2.0), float((left[1] + right[1]) / 2.0))


def features_to_head_point(features: np.ndarray) -> tuple[float, float]:
    """Head yaw/pitch from the pose terms EyeTrax appends to the feature vector."""
    yaw, pitch = float(features[-3]), float(features[-2])
    return (yaw, pitch)


def features_to_ear(features: np.ndarray, landmarks_ok: bool = True) -> float:
    """Rough open-eye score: prefer a mid open value; blink path uses EyeTrax's flag separately."""
    del features, landmarks_ok
    return 0.3


class EyeTraxGazeTracker:
    """Same open/read/close contract as GazeTracker, backed by EyeTrax."""

    backend_name = "eyetrax"

    def __init__(self, camera_index: int = 0):
        if not EYETRAX_AVAILABLE:
            raise RuntimeError("eyetrax is not installed")
        self.camera_index = camera_index
        self.cap = None
        self.blink = BlinkDetector()
        self._estimator = GazeEstimator()

    def open(self) -> bool:
        self.cap = cv2.VideoCapture(self.camera_index)
        return bool(self.cap and self.cap.isOpened())

    def close(self) -> None:
        if self.cap is not None:
            self.cap.release()
            self.cap = None
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
        payload = {
            "camera_ok": True,
            "face": False,
            "ts_ms": ts_ms,
            "frame": frame,
            "backend": self.backend_name,
        }
        try:
            features, blink_flag = self._estimator.extract_features(frame)
        except Exception:
            return payload
        if features is None:
            return payload

        ear = 0.12 if blink_flag else 0.32
        payload.update(
            {
                "face": True,
                "feature": features_to_eye_point(features),
                "head": features_to_head_point(features),
                "ear": ear,
                "blink": self.blink.update(ear, ts_ms) or bool(blink_flag),
                "eyetrax_features": np.asarray(features, dtype=float),
            }
        )
        payload["closed_ms"] = self.blink.closed_ms(ts_ms)
        return payload
