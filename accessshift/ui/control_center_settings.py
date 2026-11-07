"""Persistent, cross-platform user preferences for the AccessShift control center.

Kept independent of camera/mouse/AI modules so the UI can be developed alone.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, fields
import json
from typing import Any

from PySide6.QtCore import QSettings


@dataclass
class AccessibilitySettings:
    profile: str = "custom"
    gaze_control: bool = False
    steady_hand: bool = True
    smart_interface: bool = True
    predictive_speech: bool = False
    blink_select: bool = True
    reduce_complexity: bool = True
    tremor_strength: int = 50
    gaze_dwell_ms: int = 1100
    target_size_pct: int = 140
    font_size_pct: int = 110
    speech_rate: int = 160
    initial_setup_complete: bool = False
    assistance_enabled: bool = True

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


# IDs deliberately match accessshift/engine/profiles.py on the team's repo.
PROFILES: dict[str, dict[str, Any]] = {
    "als": {
        "label": "Hands-free control", "description": "Use your eyes, blinking and speech.",
        "gaze_control": True, "steady_hand": False, "smart_interface": True,
        "predictive_speech": True,
    },
    "parkinsons": {
        "label": "Steadier pointing", "description": "Reduce tremor and make targets easier to reach.",
        "gaze_control": False, "steady_hand": True, "smart_interface": True,
        "predictive_speech": False,
    },
    "cognitive": {
        "label": "Simplified browsing", "description": "Fewer distractions and clearer instructions.",
        "gaze_control": False, "steady_hand": False, "smart_interface": True,
        "predictive_speech": True,
    },
    "custom": {
        "label": "Personalize everything", "description": "Choose any combination of assistance.",
    },
}

PERSISTENCE_KEY = "control_center/preferences_v1"


def load_settings(store: QSettings | None = None) -> AccessibilitySettings:
    store = store or QSettings("GitHappens", "AccessShift AI")
    raw = store.value(PERSISTENCE_KEY, "")
    if not raw:
        return AccessibilitySettings()
    try:
        data = json.loads(raw)
        valid_fields = {f.name for f in fields(AccessibilitySettings)}
        data = {k: v for k, v in data.items() if k in valid_fields}
        candidate = AccessibilitySettings(**data)
        if candidate.profile not in PROFILES:
            candidate.profile = "custom"
        candidate.tremor_strength = max(0, min(100, int(candidate.tremor_strength)))
        candidate.gaze_dwell_ms = max(600, min(2000, int(candidate.gaze_dwell_ms)))
        candidate.target_size_pct = max(100, min(200, int(candidate.target_size_pct)))
        candidate.font_size_pct = max(90, min(160, int(candidate.font_size_pct)))
        candidate.speech_rate = max(100, min(220, int(candidate.speech_rate)))
        return candidate
    except (ValueError, TypeError, KeyError):
        return AccessibilitySettings()


def save_settings(state: AccessibilitySettings, store: QSettings | None = None) -> None:
    store = store or QSettings("GitHappens", "AccessShift AI")
    store.setValue(PERSISTENCE_KEY, json.dumps(state.as_dict(), sort_keys=True))
    store.sync()
