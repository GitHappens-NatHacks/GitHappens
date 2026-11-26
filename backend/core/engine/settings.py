"""Qt-free accessibility settings model and validation."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, fields
from typing import Any

VALID_PROFILES = (
    "als",
    "parkinsons",
    "cognitive",
    "custom",
    "mild",
    "moderate",
    "high",
    "hands_free",
)
VALID_BYPASS_KEYS = ("none", "alt", "shift", "ctrl", "fn")
VALID_PRECISION_KEYS = ("none", "alt", "shift", "ctrl")


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
    adaptive_smoothing: bool = True
    simulate_tremor: bool = False
    anti_drag: bool = True
    anti_drag_threshold_px: float = 8.0
    anti_drag_hold_ms: int = 300
    click_freeze_ms: int = 180
    click_debounce_ms: int = 70
    right_click_guard: bool = True
    scroll_smoothing: bool = True
    gravity_wells: bool = True
    gravity_strength: int = 35
    bypass_key: str = "alt"
    precision_key: str = "none"
    excluded_apps: list[str] = field(default_factory=list)
    global_shortcut: str = "CommandOrControl+Shift+S"
    resume_stabilization_on_launch: bool = False
    minimize_to_tray: bool = True
    keyboard_cadence_telemetry: bool = False
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
        if "excluded_apps" in filtered and not isinstance(filtered["excluded_apps"], list):
            filtered["excluded_apps"] = []
        return cls(**filtered).validated()

    def validated(self) -> AccessibilitySettings:
        if self.profile not in VALID_PROFILES:
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
        self.adaptive_smoothing = bool(self.adaptive_smoothing)
        self.anti_drag_threshold_px = round(max(2.0, min(40.0, float(self.anti_drag_threshold_px))), 1)
        self.anti_drag_hold_ms = max(80, min(1500, int(self.anti_drag_hold_ms)))
        self.click_freeze_ms = max(0, min(500, int(self.click_freeze_ms)))
        self.click_debounce_ms = max(0, min(250, int(self.click_debounce_ms)))
        self.right_click_guard = bool(self.right_click_guard)
        self.scroll_smoothing = bool(self.scroll_smoothing)
        self.gravity_strength = max(0, min(80, int(self.gravity_strength)))

        bypass = str(self.bypass_key or "alt").strip().lower()
        self.bypass_key = bypass if bypass in VALID_BYPASS_KEYS else "alt"
        precision = str(self.precision_key or "none").strip().lower()
        self.precision_key = precision if precision in VALID_PRECISION_KEYS else "none"

        if isinstance(self.excluded_apps, list):
            seen: set[str] = set()
            cleaned: list[str] = []
            for item in self.excluded_apps:
                val = str(item or "").strip()[:80]
                key = val.lower()
                if val and key not in seen:
                    seen.add(key)
                    cleaned.append(val)
            self.excluded_apps = cleaned[:50]
        else:
            self.excluded_apps = []

        shortcut = str(self.global_shortcut or "").strip()
        self.global_shortcut = shortcut[:64] if shortcut else "CommandOrControl+Shift+S"
        self.resume_stabilization_on_launch = bool(self.resume_stabilization_on_launch)
        self.minimize_to_tray = bool(self.minimize_to_tray)
        self.keyboard_cadence_telemetry = bool(self.keyboard_cadence_telemetry)

        self.gaze_dwell_ms = max(600, min(2000, int(self.gaze_dwell_ms)))
        self.target_size_pct = max(100, min(200, int(self.target_size_pct)))
        self.font_size_pct = max(90, min(160, int(self.font_size_pct)))
        self.letter_spacing_px = max(0, min(4, int(self.letter_spacing_px)))
        self.tint_opacity = max(0, min(20, int(self.tint_opacity)))
        self.speech_rate = max(100, min(220, int(self.speech_rate)))
        self.screen_width = max(320, int(self.screen_width))
        self.screen_height = max(240, int(self.screen_height))
        return self
