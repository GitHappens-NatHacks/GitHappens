"""Webcam resting-hand tremor detector with MediaPipe Hands + OpenCV optical-flow fallback.

Captures 4-6 Hz resting tremor and 6-12 Hz postural/action tremor from a resting hand
placed in view of the laptop webcam, without requiring mouse contact.

Backend selection:
- Uses MediaPipe Hand Landmarker (21 3D landmarks) when ``mediapipe`` is installed
  (Python 3.10-3.12 and packaged PyInstaller builds).
- Automatically falls back to OpenCV pyramidal Lucas-Kanade sparse optical flow
  (``cv2.goodFeaturesToTrack`` + ``cv2.calcOpticalFlowPyrLK``) inside a centered hand
  ROI so Python 3.13+ environments and MediaPipe-free setups still work cleanly.
"""

from __future__ import annotations

import math
import sys
import time
from typing import Any, Literal

import numpy as np
from scipy import signal as scipy_signal

VisionBackend = Literal["auto", "mediapipe", "opencv"]


def detect_vision_capabilities() -> dict[str, Any]:
    """Report installed computer-vision backends for webcam resting-hand checks."""
    has_cv2 = False
    has_mp_hands = False
    try:
        import cv2  # noqa: F401

        has_cv2 = True
    except Exception:
        has_cv2 = False

    try:
        import mediapipe as mp  # type: ignore[import-untyped]

        has_mp_hands = hasattr(mp, "solutions") and hasattr(mp.solutions, "hands")
    except Exception:
        has_mp_hands = False

    if has_mp_hands:
        active_backend = "mediapipe_hands"
    elif has_cv2:
        active_backend = "opencv_optical_flow"
    else:
        active_backend = "unavailable"

    return {
        "python_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        "opencv_available": has_cv2,
        "mediapipe_hands_available": has_mp_hands,
        "selected_resting_hand_backend": active_backend,
    }


class OpenCVOpticalFlowHandTracker:
    """Tracks micro-oscillations inside a hand ROI using pyramidal Lucas-Kanade optical flow."""

    def __init__(self, *, max_corners: int = 40, roi_fraction: float = 0.5):
        import cv2

        self._cv2 = cv2
        self._max_corners = max(8, int(max_corners))
        self._roi_fraction = max(0.2, min(0.95, float(roi_fraction)))
        self._prev_gray: np.ndarray | None = None
        self._prev_pts: np.ndarray | None = None
        self._cum_x = 0.0
        self._cum_y = 0.0
        self._roi_bounds: tuple[int, int, int, int] | None = None

    @property
    def backend_name(self) -> str:
        return "opencv_optical_flow"

    def _extract_roi_gray(self, frame_bgr: np.ndarray) -> np.ndarray:
        cv2 = self._cv2
        if frame_bgr.ndim == 3:
            gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
        else:
            gray = frame_bgr.astype(np.uint8, copy=False)
        h, w = gray.shape[:2]
        rw = max(32, int(w * self._roi_fraction))
        rh = max(32, int(h * self._roi_fraction))
        x0 = (w - rw) // 2
        y0 = (h - rh) // 2
        self._roi_bounds = (x0, y0, rw, rh)
        return gray[y0 : y0 + rh, x0 : x0 + rw]

    def _seed_corners(self, roi_gray: np.ndarray) -> np.ndarray | None:
        cv2 = self._cv2
        pts = cv2.goodFeaturesToTrack(
            roi_gray,
            maxCorners=self._max_corners,
            qualityLevel=0.05,
            minDistance=6,
            blockSize=7,
        )
        return pts

    def process_frame(self, frame_bgr: np.ndarray) -> tuple[float, float] | None:
        """Process one BGR/grayscale video frame and return cumulative ROI displacement (px)."""
        cv2 = self._cv2
        roi_gray = self._extract_roi_gray(frame_bgr)

        if self._prev_gray is None or self._prev_pts is None or len(self._prev_pts) < 4:
            self._prev_gray = roi_gray
            self._prev_pts = self._seed_corners(roi_gray)
            return (self._cum_x, self._cum_y) if self._prev_pts is not None else None

        next_pts, status, _err = cv2.calcOpticalFlowPyrLK(
            self._prev_gray,
            roi_gray,
            self._prev_pts,
            None,
            winSize=(15, 15),
            maxLevel=2,
            criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 10, 0.03),
        )

        if next_pts is None or status is None:
            self._prev_gray = roi_gray
            self._prev_pts = self._seed_corners(roi_gray)
            return (self._cum_x, self._cum_y)

        valid = status.reshape(-1) == 1
        good_old = self._prev_pts.reshape(-1, 2)[valid]
        good_new = next_pts.reshape(-1, 2)[valid]

        if len(good_new) >= 3:
            deltas = good_new - good_old
            # Median delta rejects stray background edges and outlier reflections
            med_dx = float(np.median(deltas[:, 0]))
            med_dy = float(np.median(deltas[:, 1]))
            # Guard against abrupt whole-frame jumps
            if math.hypot(med_dx, med_dy) <= 45.0:
                self._cum_x += med_dx
                self._cum_y += med_dy
            self._prev_pts = good_new.reshape(-1, 1, 2)
        else:
            self._prev_pts = self._seed_corners(roi_gray)

        # Periodically replenish corners if tracking set shrinks
        if self._prev_pts is None or len(self._prev_pts) < max(6, self._max_corners // 4):
            fresh = self._seed_corners(roi_gray)
            if fresh is not None:
                self._prev_pts = fresh

        self._prev_gray = roi_gray
        return (self._cum_x, self._cum_y)

    def close(self) -> None:
        self._prev_gray = None
        self._prev_pts = None


class MediaPipeHandTremorTracker:
    """Tracks 21 MediaPipe hand landmarks (wrist + thumb/index tips) in RGB frames."""

    def __init__(self) -> None:
        import cv2
        import mediapipe as mp  # type: ignore[import-untyped]

        self._cv2 = cv2
        self._hands = mp.solutions.hands.Hands(
            static_image_mode=False,
            max_num_hands=1,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5,
        )

    @property
    def backend_name(self) -> str:
        return "mediapipe_hands"

    def process_frame(self, frame_bgr: np.ndarray) -> tuple[float, float] | None:
        h, w = frame_bgr.shape[:2]
        rgb = self._cv2.cvtColor(frame_bgr, self._cv2.COLOR_BGR2RGB)
        res = self._hands.process(rgb)
        if not res.multi_hand_landmarks:
            return None
        lms = res.multi_hand_landmarks[0].landmark
        # Weighted blend of wrist (0), thumb tip (4), and index tip (8) captures resting & pill-rolling tremor
        xs = (lms[0].x * 0.4 + lms[4].x * 0.3 + lms[8].x * 0.3) * float(w)
        ys = (lms[0].y * 0.4 + lms[4].y * 0.3 + lms[8].y * 0.3) * float(h)
        return (float(xs), float(ys))

    def close(self) -> None:
        try:
            self._hands.close()
        except Exception:
            pass


def create_resting_hand_tracker(
    prefer_backend: VisionBackend = "auto",
) -> MediaPipeHandTremorTracker | OpenCVOpticalFlowHandTracker:
    """Instantiate MediaPipe hand tracker or fall back cleanly to OpenCV optical flow."""
    if prefer_backend == "opencv":
        return OpenCVOpticalFlowHandTracker()

    if prefer_backend in ("auto", "mediapipe"):
        try:
            return MediaPipeHandTremorTracker()
        except Exception:
            if prefer_backend == "mediapipe":
                raise
    return OpenCVOpticalFlowHandTracker()


def score_resting_hand_samples(
    samples: list[dict[str, float]],
    *,
    backend_used: str = "opencv_optical_flow",
    pixels_per_mm: float = 3.78,
    context_tag: str = "resting_hand",
    notes: str = "",
) -> dict[str, Any]:
    """Compute 4-6 Hz resting vs 6-12 Hz action Welch PSD metrics from webcam hand samples."""
    if len(samples) < 20:
        raise ValueError("At least 20 frames are required to score a resting-hand tremor check.")

    ordered = sorted(samples, key=lambda s: float(s.get("t", 0.0)))
    times = np.asarray([float(s["t"]) for s in ordered], dtype=np.float64)
    xs = np.asarray([float(s["x"]) for s in ordered], dtype=np.float64)
    ys = np.asarray([float(s["y"]) for s in ordered], dtype=np.float64)

    duration_sec = float(times[-1] - times[0])
    if duration_sec < 1.0:
        raise ValueError("Resting-hand capture must span at least 1.0 second.")

    # Resample onto uniform 30 Hz grid (Nyquist 15 Hz covers 4-12 Hz tremor cleanly)
    fs = 30.0
    grid = np.arange(times[0], times[-1], 1.0 / fs)
    if len(grid) < 32:
        raise ValueError("Not enough resampled points for spectral tremor analysis.")

    nperseg = min(len(grid), 128)
    hz: np.ndarray | None = None
    power: np.ndarray | None = None
    detrended_axes: list[np.ndarray] = []

    for axis in (xs, ys):
        vals = np.interp(grid, times, axis)
        vals -= np.linspace(vals[0], vals[-1], len(vals))
        vals -= vals.mean()
        detrended_axes.append(vals)
        freqs, psd = scipy_signal.welch(
            vals,
            fs=fs,
            window="hann",
            nperseg=nperseg,
            noverlap=nperseg // 2,
            detrend=False,
        )
        hz = freqs
        power = psd if power is None else (power + psd)

    assert hz is not None and power is not None

    # Bandpass 4-12 Hz RMS displacement via rFFT
    rfft_freqs = np.fft.rfftfreq(len(grid), d=1.0 / fs)
    bp_mask = (rfft_freqs >= 4.0) & (rfft_freqs <= 12.0)
    sx = np.fft.rfft(detrended_axes[0])
    sy = np.fft.rfft(detrended_axes[1])
    sx[~bp_mask] = 0.0
    sy[~bp_mask] = 0.0
    bx = np.fft.irfft(sx, n=len(grid))
    by = np.fft.irfft(sy, n=len(grid))
    rms_px = float(np.sqrt(np.mean(bx * bx + by * by)))
    rms_mm = rms_px / max(1.0, float(pixels_per_mm))

    broad_mask = (hz >= 0.5) & (hz <= 14.5)
    rest_mask = (hz >= 4.0) & (hz < 6.0)
    act_mask = (hz >= 6.0) & (hz <= 12.0)
    tremor_mask = (hz >= 4.0) & (hz <= 12.0)

    total_pow = float(np.sum(power[broad_mask]))
    if total_pow > 1e-9:
        resting_pct = (float(np.sum(power[rest_mask])) / total_pow) * 100.0
        action_pct = (float(np.sum(power[act_mask])) / total_pow) * 100.0
        tremor_pct = resting_pct + action_pct
    else:
        resting_pct = 0.0
        action_pct = 0.0
        tremor_pct = 0.0

    # Report dominant peak frequency when non-trivial oscillation exists in 4-12 Hz
    tremor_bins = power[tremor_mask]
    tremor_freqs = hz[tremor_mask]
    if len(tremor_bins) > 0 and rms_px >= 0.35 and tremor_pct >= 12.0:
        dominant_hz: float | None = round(float(tremor_freqs[int(np.argmax(tremor_bins))]), 2)
    else:
        dominant_hz = None

    # Combine amplitude and spectral band concentration into a 0-100 stability score
    amp_penalty = min(65.0, rms_mm * 16.0)
    spectral_penalty = min(35.0, tremor_pct * 0.45) if rms_px >= 0.35 else 0.0
    stability_score = round(max(0.0, min(100.0, 100.0 - amp_penalty - spectral_penalty)), 2)

    backend_note = f"Webcam resting-hand check ({backend_used})"
    full_notes = f"{backend_note}: {notes.strip()}" if notes.strip() else backend_note

    return {
        "context_tag": str(context_tag or "resting_hand").strip()[:40],
        "duration_sec": round(duration_sec, 2),
        "overall_score": stability_score,
        "hold_stability_score": stability_score,
        "hold_rms_px": round(rms_px, 2),
        "hold_rms_mm": round(rms_mm, 3),
        "hold_dominant_hz": dominant_hz,
        "hold_resting_band_pct": round(resting_pct, 2),
        "hold_action_band_pct": round(action_pct, 2),
        "hold_tremor_index": round(tremor_pct, 2),
        "tap_count": 0,
        "tap_accuracy_pct": None,
        "tap_mean_error_px": None,
        "tap_mean_reaction_ms": None,
        "backend_used": backend_used,
        "notes": full_notes[:400],
    }


def run_webcam_resting_check(
    *,
    duration_sec: float = 10.0,
    camera_index: int = 0,
    prefer_backend: VisionBackend = "auto",
    context_tag: str = "resting_hand",
    notes: str = "",
) -> dict[str, Any]:
    """Capture frames from the local webcam and score resting hand tremor."""
    import cv2

    tracker = create_resting_hand_tracker(prefer_backend=prefer_backend)
    cap = cv2.VideoCapture(int(camera_index))
    if not cap.isOpened():
        tracker.close()
        raise RuntimeError(f"Unable to open webcam index {camera_index}.")

    samples: list[dict[str, float]] = []
    start = time.monotonic()
    target_duration = max(2.0, min(30.0, float(duration_sec)))
    try:
        while (time.monotonic() - start) < target_duration:
            ok, frame = cap.read()
            if not ok or frame is None:
                time.sleep(0.01)
                continue
            pt = tracker.process_frame(frame)
            if pt is not None:
                samples.append({
                    "x": pt[0],
                    "y": pt[1],
                    "t": time.monotonic() - start,
                })
    finally:
        cap.release()
        tracker.close()

    return score_resting_hand_samples(
        samples,
        backend_used=tracker.backend_name,
        context_tag=context_tag,
        notes=notes,
    )
