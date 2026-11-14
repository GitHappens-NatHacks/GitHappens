"""User accessibility profiles for the Adaptive Interaction Engine."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field


@dataclass
class ModuleFlags:
    gaze_control: bool = False
    smart_interface: bool = False
    steady_hand: bool = False
    predictive_speech: bool = False


@dataclass
class Profile:
    id: str
    label: str
    modules: ModuleFlags = field(default_factory=ModuleFlags)


PROFILES: dict[str, Profile] = {
    "als": Profile(
        id="als",
        label="ALS / severe motor impairment",
        modules=ModuleFlags(
            gaze_control=True,
            smart_interface=True,
            steady_hand=False,
            predictive_speech=True,
        ),
    ),
    "parkinsons": Profile(
        id="parkinsons",
        label="Parkinson's / essential tremor",
        modules=ModuleFlags(
            gaze_control=False,
            smart_interface=True,
            steady_hand=True,
            predictive_speech=False,
        ),
    ),
    "mild": Profile(
        id="mild",
        label="Mild Tremor (Responsive)",
        modules=ModuleFlags(
            gaze_control=False,
            smart_interface=True,
            steady_hand=True,
            predictive_speech=False,
        ),
    ),
    "moderate": Profile(
        id="moderate",
        label="Moderate Tremor (Balanced)",
        modules=ModuleFlags(
            gaze_control=False,
            smart_interface=True,
            steady_hand=True,
            predictive_speech=False,
        ),
    ),
    "high": Profile(
        id="high",
        label="High Tremor (Maximum Stabilization)",
        modules=ModuleFlags(
            gaze_control=False,
            smart_interface=True,
            steady_hand=True,
            predictive_speech=False,
        ),
    ),
    "hands_free": Profile(
        id="hands_free",
        label="Hands-Free (Gaze Mode)",
        modules=ModuleFlags(
            gaze_control=True,
            smart_interface=True,
            steady_hand=False,
            predictive_speech=True,
        ),
    ),
    "cognitive": Profile(
        id="cognitive",
        label="Cognitive accessibility",
        modules=ModuleFlags(
            gaze_control=False,
            smart_interface=True,
            steady_hand=False,
            predictive_speech=True,
        ),
    ),
    "custom": Profile(
        id="custom",
        label="Custom mix",
        modules=ModuleFlags(),
    ),
}


def get_profile(profile_id: str) -> Profile:
    base = PROFILES.get(profile_id, PROFILES["custom"])
    return Profile(id=base.id, label=base.label, modules=deepcopy(base.modules))
