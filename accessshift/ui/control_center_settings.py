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
    tremor_strength: int = 95
    tremor_intensity: int = 55  # demo sim scale: 0 mild through 100 intense
    gaze_dwell_ms: int = 1100  # Normal speed (Relaxed 1.6 s, Normal 1.1 s, Quick 0.8 s)
    target_size_pct: int = 140
    font_size_pct: int = 110
    color_profile: str = "standard"
    letter_spacing_px: int = 0
    word_highlight: bool = False  # reading focus aid: highlight the word under the pointer
    tint_color: str = "warm"
    tint_opacity: int = 10
    speech_rate: int = 160
    initial_setup_complete: bool = False
    assistance_enabled: bool = True

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


# IDs deliberately match accessshift/engine/profiles.py on the team's repo.
PROFILES: dict[str, dict[str, Any]] = {
    "als": {
        "label": "Hands-free control", "description": "Use head movement, blinking and speech.",
        "gaze_control": True, "steady_hand": False, "smart_interface": True,
        "predictive_speech": True,
    },
    "parkinsons": {
        "label": "Steadier pointing", "description": "Reduce tremor and make targets easier to reach.",
        "gaze_control": False, "steady_hand": True, "smart_interface": True,
        "predictive_speech": False,
    },
    "cognitive": {
        "label": "Clearer interfaces", "description": "Fewer distractions in supported demo layouts.",
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
        candidate.tremor_strength = max(0, min(200, int(candidate.tremor_strength)))
        candidate.tremor_intensity = max(0, min(100, int(getattr(candidate, "tremor_intensity", 55))))
        candidate.gaze_dwell_ms = max(600, min(2000, int(candidate.gaze_dwell_ms)))
        candidate.target_size_pct = max(100, min(200, int(candidate.target_size_pct)))
        candidate.font_size_pct = max(90, min(160, int(candidate.font_size_pct)))
        candidate.speech_rate = max(100, min(220, int(candidate.speech_rate)))
        candidate.letter_spacing_px = max(0, min(4, int(candidate.letter_spacing_px)))
        candidate.tint_opacity = max(0, min(20, int(candidate.tint_opacity)))
        if candidate.color_profile not in ("standard", "high_contrast", "warm", "cool"):
            candidate.color_profile = "standard"
        if candidate.tint_color not in ("warm", "cool", "rose"):
            candidate.tint_color = "warm"
        return candidate
    except (ValueError, TypeError, KeyError):
        return AccessibilitySettings()


def save_settings(state: AccessibilitySettings, store: QSettings | None = None) -> None:
    store = store or QSettings("GitHappens", "AccessShift AI")
    store.setValue(PERSISTENCE_KEY, json.dumps(state.as_dict(), sort_keys=True))
    store.sync()
