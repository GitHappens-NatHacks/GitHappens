"""Qt-free accessibility settings model and validation."""

from __future__ import annotations

from dataclasses import asdict, dataclass, fields
from typing import Any


@dataclass
class AccessibilitySettings:
    profile: str = "parkinsons"
    assistance_enabled: bool = True
    gaze_control: bool = False
    steady_hand: bool = True
    smart_interface: bool = True
    predictive_speech: bool = False
    blink_select: bool = True
    reduce_complexity: bool = True
    tremor_strength: int = 95
    tremor_intensity: int = 55
    one_euro_min_cutoff: float = 0.65
    one_euro_beta: float = 0.004
    simulate_tremor: bool = False
    anti_drag: bool = True
    anti_drag_threshold_px: float = 8.0
    anti_drag_hold_ms: int = 300
    system_mouse: bool = False
    gaze_source: str = "head"
    gaze_dwell_ms: int = 1100
    target_size_pct: int = 140
    font_size_pct: int = 110
    color_profile: str = "standard"
    letter_spacing_px: int = 0
    tint_color: str = "warm"
    tint_opacity: int = 10
    speech_rate: int = 160
    screen_width: int = 1440
    screen_height: int = 900

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, raw: dict[str, Any] | None) -> AccessibilitySettings:
        if not raw:
            return cls().validated()
        valid = {f.name for f in fields(cls)}
        filtered = {k: v for k, v in raw.items() if k in valid}
        return cls(**filtered).validated()

    def validated(self) -> AccessibilitySettings:
        if self.profile not in ("als", "parkinsons", "cognitive", "custom"):
            self.profile = "custom"
        if self.gaze_source not in ("head", "eyes"):
            self.gaze_source = "head"
        if self.color_profile not in ("standard", "high_contrast", "warm", "cool"):
            self.color_profile = "standard"
        if self.tint_color not in ("warm", "cool", "rose"):
            self.tint_color = "warm"
        self.tremor_strength = max(0, min(200, int(self.tremor_strength)))
        self.tremor_intensity = max(0, min(100, int(self.tremor_intensity)))
        self.one_euro_min_cutoff = round(max(0.05, min(5.0, float(self.one_euro_min_cutoff))), 4)
        self.one_euro_beta = round(max(0.0, min(0.2, float(self.one_euro_beta))), 5)
        self.anti_drag_threshold_px = round(max(2.0, min(40.0, float(self.anti_drag_threshold_px))), 1)
        self.anti_drag_hold_ms = max(100, min(1500, int(self.anti_drag_hold_ms)))
        self.gaze_dwell_ms = max(600, min(2000, int(self.gaze_dwell_ms)))
        self.target_size_pct = max(100, min(200, int(self.target_size_pct)))
        self.font_size_pct = max(90, min(160, int(self.font_size_pct)))
        self.letter_spacing_px = max(0, min(4, int(self.letter_spacing_px)))
        self.tint_opacity = max(0, min(20, int(self.tint_opacity)))
        self.speech_rate = max(100, min(220, int(self.speech_rate)))
        self.screen_width = max(320, int(self.screen_width))
        self.screen_height = max(240, int(self.screen_height))
        return self
