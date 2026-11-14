"""Qt-free gaze and head-tracking module exports."""

from backend.core.gaze.blink import BlinkDetector, eye_aspect_ratio
from backend.core.gaze.calibration import (
    CALIBRATION_POINTS,
    HEAD_POSES,
    DotCollector,
    GazeCalibration,
    head_calibration,
)
from backend.core.gaze.controller import GazeController, GazeTarget, ScreenRect
from backend.core.gaze.dwell import DwellSelector, DwellState
from backend.core.gaze.metrics import GazeMetrics
from backend.core.gaze.tracker import BACKENDS, GazeTracker, create_tracker, resolve_backend
from backend.core.gaze.worker import GazeWorker

__all__ = [
    "BACKENDS",
    "BlinkDetector",
    "CALIBRATION_POINTS",
    "DotCollector",
    "DwellSelector",
    "DwellState",
    "GazeCalibration",
    "GazeController",
    "GazeMetrics",
    "GazeTarget",
    "GazeTracker",
    "GazeWorker",
    "HEAD_POSES",
    "ScreenRect",
    "create_tracker",
    "eye_aspect_ratio",
    "head_calibration",
    "resolve_backend",
]
