"""Accessibility engine coordination, profiles, and settings."""

from backend.core.engine.coordinator import AdaptiveEngine, EngineCoordinator
from backend.core.engine.profiles import ModuleFlags, Profile, get_profile
from backend.core.engine.settings import AccessibilitySettings

__all__ = [
    "AccessibilitySettings",
    "AdaptiveEngine",
    "EngineCoordinator",
    "ModuleFlags",
    "Profile",
    "get_profile",
]
