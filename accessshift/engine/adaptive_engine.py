"""Coordinates which accessibility modules are active for the current profile."""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal

from accessshift.engine.profiles import ModuleFlags, Profile, get_profile


class AdaptiveEngine(QObject):
    profile_changed = Signal(str)
    modules_changed = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._profile: Profile = get_profile("parkinsons")

    @property
    def profile(self) -> Profile:
        return self._profile

    @property
    def modules(self) -> ModuleFlags:
        return self._profile.modules

    def set_profile(self, profile_id: str) -> None:
        self._profile = get_profile(profile_id)
        self.profile_changed.emit(self._profile.id)
        self.modules_changed.emit(self._profile.modules)

    def set_module(self, name: str, enabled: bool) -> None:
        if not hasattr(self._profile.modules, name):
            raise AttributeError(f"Unknown module flag: {name}")
        setattr(self._profile.modules, name, enabled)
        self.modules_changed.emit(self._profile.modules)
