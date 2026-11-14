"""Webcam gaze tracking.

Default backend is MediaPipe Face Mesh. Optional EyeTrax is used for eye
features only (hybrid). Head pointing always uses the original MediaPipe
nose-to-eye-corner signal.
"""

from __future__ import annotations

import os
import time

import cv2
import mediapipe as mp
import numpy as np

from backend.core.gaze.blink import BlinkDetector, eye_aspect_ratio
from backend.core.gaze.features import LEFT_EYE, RIGHT_EYE, gaze_feature, head_feature

BACKENDS = ("auto", "mediapipe", "eyetrax", "hybrid")


def normalize_frame_lighting(frame: np.ndarray) -> tuple[np.ndarray, str, float]:
    """Stabilize extreme dark/backlit webcam frames via YCrCb CLAHE and classify luma.

    Returns (normalized_bgr, lighting_quality, mean_luma) where lighting_quality is one of:
    'ok', 'low_light', 'backlit', or 'overexposed'.
    """
    if frame is None or frame.size == 0:
        return frame, "ok", 128.0

    ycrcb = cv2.cvtColor(frame, cv2.COLOR_BGR2YCrCb)
    y_chan = ycrcb[:, :, 0]
    h, w = y_chan.shape[:2]
    mean_luma = float(np.mean(y_chan[::4, ::4]))

    y0, y1 = h // 4, max(h // 4 + 1, (3 * h) // 4)
    x0, x1 = w // 4, max(w // 4 + 1, (3 * w) // 4)
    center_luma = float(np.mean(y_chan[y0:y1:2, x0:x1:2]))

    if mean_luma < 68.0:
        quality = "low_light"
    elif mean_luma > 215.0:
        quality = "overexposed"
    elif mean_luma - center_luma > 32.0 and center_luma < 92.0 and mean_luma > 125.0:
        quality = "backlit"
    else:
        quality = "ok"

    if quality in ("low_light", "backlit"):
        gamma = 0.72 if quality == "backlit" else 0.78
        lifted = np.clip(((y_chan.astype(np.float32) / 255.0) ** gamma) * 255.0, 0, 255).astype(
            np.uint8
        )
        clahe = cv2.createCLAHE(clipLimit=2.2, tileGridSize=(8, 8))
        ycrcb[:, :, 0] = clahe.apply(lifted)
        return cv2.cvtColor(ycrcb, cv2.COLOR_YCrCb2BGR), quality, mean_luma

    return frame, quality, mean_luma


class GazeTracker:
    """MediaPipe Face Mesh tracker (reliable fallback). Head and eyes."""

    backend_name = "mediapipe"

    def __init__(self, camera_index: int = 0):
        self.camera_index = camera_index
        self.cap = None
        self.blink = BlinkDetector()
        self._mesh = mp.solutions.face_mesh.FaceMesh(
            max_num_faces=1,
            refine_landmarks=True,  # adds the iris landmarks 468-477
            min_detection_confidence=0.6,
            min_tracking_confidence=0.3,  # keep tracking a turned head (detection stays strict)
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
            return {"camera_ok": False, "face": False, "ts_ms": ts_ms, "backend": self.backend_name}

        frame = cv2.flip(frame, 1)
        h, w = frame.shape[:2]
        processed, lighting_quality, luma = normalize_frame_lighting(frame)
        result = self._mesh.process(cv2.cvtColor(processed, cv2.COLOR_BGR2RGB))
        payload = {
            "camera_ok": True,
            "face": False,
            "ts_ms": ts_ms,
            "frame": frame,
            "backend": self.backend_name,
            "lighting_quality": lighting_quality,
            "luma": round(luma, 1),
        }

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


def resolve_backend(name: str | None = None) -> str:
    raw = (name or os.getenv("GAZE_BACKEND", "auto")).strip().lower()
    if raw not in BACKENDS:
        raise ValueError(f"GAZE_BACKEND must be one of {BACKENDS}, got {raw!r}")
    return raw


def create_tracker(camera_index: int = 0, backend: str | None = None):
    """Build a tracker.

    Head pointing always uses MediaPipe (original method).
    auto / eyetrax / hybrid: MediaPipe head + EyeTrax eye features when available.
    mediapipe: MediaPipe for both.
    """
    choice = resolve_backend(backend)

    if choice == "mediapipe":
        return GazeTracker(camera_index)

    # auto, eyetrax, and hybrid all keep MediaPipe head; EyeTrax only upgrades eyes.
    try:
        from backend.core.gaze.hybrid_tracker import HybridGazeTracker

        return HybridGazeTracker(camera_index)
    except Exception as exc:
        if choice == "eyetrax":
            raise RuntimeError(
                "EyeTrax eye tracking requested but could not start "
                f"({exc}). Install eyetrax or set GAZE_BACKEND=mediapipe."
            ) from exc
        return GazeTracker(camera_index)
