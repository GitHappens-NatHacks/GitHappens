"""Qt-free SteadyHand stabilization, FFT telemetry, and target selection exports."""

from backend.core.steadyhand.controller import SteadyHandController
from backend.core.steadyhand.exclusions import ActiveAppMonitor, match_excluded_app
from backend.core.steadyhand.filter import (
    ClickBounceGuard,
    IntentionalHold,
    OneEuroFilter,
    ScrollJitterFilter,
)
from backend.core.steadyhand.metrics import Click, MotorTelemetry, Trial, save_results
from backend.core.steadyhand.targets import Target, TargetManager
from backend.core.steadyhand.worker import SteadyHandWorker

__all__ = [
    "ActiveAppMonitor",
    "Click",
    "ClickBounceGuard",
    "IntentionalHold",
    "MotorTelemetry",
    "OneEuroFilter",
    "ScrollJitterFilter",
    "SteadyHandController",
    "SteadyHandWorker",
    "Target",
    "TargetManager",
    "Trial",
    "match_excluded_app",
    "save_results",
]
