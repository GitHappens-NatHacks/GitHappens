"""Pydantic request and response schemas for the TrueCursor FastAPI service."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class SettingsPayload(BaseModel):
    profile: str
    assistance_enabled: bool
    gaze_control: bool
    steady_hand: bool
    smart_interface: bool
    predictive_speech: bool
    blink_select: bool
    reduce_complexity: bool
    tremor_strength: int
    tremor_intensity: int
    simulate_tremor: bool
    anti_drag: bool
    system_mouse: bool
    gaze_source: str
    gaze_dwell_ms: int
    target_size_pct: int
    font_size_pct: int
    color_profile: str
    letter_spacing_px: int
    tint_color: str
    tint_opacity: int
    speech_rate: int
    screen_width: int
    screen_height: int


class SettingsUpdateRequest(BaseModel):
    profile: str | None = None
    assistance_enabled: bool | None = None
    gaze_control: bool | None = None
    steady_hand: bool | None = None
    smart_interface: bool | None = None
    predictive_speech: bool | None = None
    blink_select: bool | None = None
    reduce_complexity: bool | None = None
    tremor_strength: int | None = Field(default=None, ge=0, le=200)
    tremor_intensity: int | None = Field(default=None, ge=0, le=100)
    simulate_tremor: bool | None = None
    anti_drag: bool | None = None
    system_mouse: bool | None = None
    gaze_source: Literal["head", "eyes"] | None = None
    gaze_dwell_ms: int | None = Field(default=None, ge=600, le=2000)
    target_size_pct: int | None = Field(default=None, ge=100, le=200)
    font_size_pct: int | None = Field(default=None, ge=90, le=160)
    color_profile: str | None = None
    letter_spacing_px: int | None = Field(default=None, ge=0, le=4)
    tint_color: str | None = None
    tint_opacity: int | None = Field(default=None, ge=0, le=20)
    speech_rate: int | None = Field(default=None, ge=100, le=220)
    screen_width: int | None = Field(default=None, ge=320)
    screen_height: int | None = Field(default=None, ge=240)


class CalibrateRequest(BaseModel):
    mode: Literal["dots", "head"] = "head"
    source: Literal["head", "eyes"] = "head"
    profile_name: str = "default"
    features: list[tuple[float, float]] | None = None
    targets: list[tuple[float, float]] | None = None
    poses: dict[str, tuple[float, float]] | None = None
    open_ears: list[float] | None = None


class CalibrateResponse(BaseModel):
    profile_id: int
    source: str
    error_px: float
    calibrated: bool


class EngineToggleRequest(BaseModel):
    assistance_enabled: bool | None = None
    steady_hand: bool | None = None
    gaze_control: bool | None = None
    simulate_tremor: bool | None = None
    system_mouse: bool | None = None
    camera: bool | None = None
    camera_index: int = Field(default=0, ge=0)


class EngineToggleResponse(BaseModel):
    settings: SettingsPayload
    camera_running: bool
    steadyhand_running: bool


class PointerSampleRequest(BaseModel):
    x: float
    y: float
    timestamp: float | None = None
    pressed: bool | None = None
