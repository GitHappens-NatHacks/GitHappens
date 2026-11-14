"""OS Accessibility target detection ("gravity wells") with expanded hitboxes.

Queries interactive controls via macOS Accessibility (ApplicationServices) or
Windows UI Automation fallback, expanding effective target envelopes by 2.5x-3x
and gently pulling slowed pointers toward nearby interactive button centers.
"""

from __future__ import annotations

import math
import sys
import threading
import time
from dataclasses import dataclass
from typing import Iterable

INTERACTIVE_AX_ROLES = frozenset(
    {
        "AXButton",
        "AXCloseButton",
        "AXMenuItem",
        "AXMenuBarItem",
        "AXLink",
        "AXCheckBox",
        "AXRadioButton",
        "AXPopUpButton",
    }
)


@dataclass(frozen=True)
class GravityTarget:
    """Normalized representation of an interactive OS Accessibility element."""

    role: str
    x: float
    y: float
    width: float
    height: float
    title: str = ""

    @property
    def center(self) -> tuple[float, float]:
        return (self.x + self.width * 0.5, self.y + self.height * 0.5)

    def expanded_contains(self, px: float, py: float, expansion: float = 2.5) -> bool:
        half_w = self.width * 0.5 * expansion
        half_h = self.height * 0.5 * expansion
        cx, cy = self.center
        return (cx - half_w) <= px <= (cx + half_w) and (cy - half_h) <= py <= (cy + half_h)

    def normalized_distance(self, px: float, py: float, expansion: float = 2.5) -> float:
        half_w = max(1.0, self.width * 0.5 * expansion)
        half_h = max(1.0, self.height * 0.5 * expansion)
        cx, cy = self.center
        return math.hypot((px - cx) / half_w, (py - cy) / half_h)


def _macos_ax_probe(x: float, y: float) -> list[GravityTarget]:
    """Sample interactive AX elements under and immediately around (x, y)."""
    try:
        import ApplicationServices as AS  # type: ignore[import-not-found]
    except Exception:
        return []

    if hasattr(AS, "AXIsProcessTrusted") and not AS.AXIsProcessTrusted():
        return []

    sys_elem = AS.AXUIElementCreateSystemWide()
    offsets = ((0.0, 0.0), (-36.0, 0.0), (36.0, 0.0), (0.0, -28.0), (0.0, 28.0))
    seen: dict[tuple[str, int, int, int, int], GravityTarget] = {}

    for dx, dy in offsets:
        err, elem = AS.AXUIElementCopyElementAtPosition(sys_elem, float(x + dx), float(y + dy), None)
        if err != 0 or elem is None:
            continue
        role_err, role = AS.AXUIElementCopyAttributeValue(elem, "AXRole", None)
        if role_err != 0 or role not in INTERACTIVE_AX_ROLES:
            continue
        pos_err, pos_val = AS.AXUIElementCopyAttributeValue(elem, "AXPosition", None)
        size_err, size_val = AS.AXUIElementCopyAttributeValue(elem, "AXSize", None)
        if pos_err != 0 or size_err != 0 or pos_val is None or size_val is None:
            continue
        ok_pos, pt = AS.AXValueGetValue(pos_val, AS.kAXValueCGPointType, None)
        ok_size, sz = AS.AXValueGetValue(size_val, AS.kAXValueCGSizeType, None)
        if not ok_pos or not ok_size:
            continue
        w, h = float(sz.width), float(sz.height)
        if w <= 2.0 or h <= 2.0 or w > 640.0 or h > 220.0:
            continue
        title = ""
        t_err, t_val = AS.AXUIElementCopyAttributeValue(elem, "AXTitle", None)
        if t_err == 0 and isinstance(t_val, str):
            title = t_val[:48]
        gx, gy = float(pt.x), float(pt.y)
        key = (str(role), round(gx), round(gy), round(w), round(h))
        seen[key] = GravityTarget(role=str(role), x=gx, y=gy, width=w, height=h, title=title)

    return list(seen.values())


INTERACTIVE_UIA_CONTROLS = frozenset(
    {
        "ButtonControl",
        "CheckBoxControl",
        "RadioButtonControl",
        "HyperlinkControl",
        "MenuItemControl",
        "ComboBoxControl",
        "TabItemControl",
        "SplitButtonControl",
    }
)


def _windows_uia_probe(x: float, y: float) -> list[GravityTarget]:
    """Query interactive UI Automation elements around (x, y) on Windows."""
    try:
        import uiautomation as auto  # type: ignore[import-not-found]
    except Exception:
        return []

    offsets = ((0.0, 0.0), (-32.0, 0.0), (32.0, 0.0), (0.0, -24.0), (0.0, 24.0))
    seen: dict[tuple[str, int, int, int, int], GravityTarget] = {}
    for dx, dy in offsets:
        try:
            ctrl = auto.ControlFromPoint(int(round(x + dx)), int(round(y + dy)))
            if ctrl is None:
                continue
            role = str(getattr(ctrl, "ControlTypeName", "") or "")
            if INTERACTIVE_UIA_CONTROLS and role and role not in INTERACTIVE_UIA_CONTROLS:
                continue
            rect = ctrl.BoundingRectangle
            w = float(rect.right - rect.left)
            h = float(rect.bottom - rect.top)
            if w <= 2.0 or h <= 2.0 or w > 640.0 or h > 220.0:
                continue
            gx, gy = float(rect.left), float(rect.top)
            title = str(getattr(ctrl, "Name", "") or "")[:48]
            key = (role or "Button", round(gx), round(gy), round(w), round(h))
            seen[key] = GravityTarget(
                role=role or "Button", x=gx, y=gy, width=w, height=h, title=title
            )
        except Exception:
            continue
    return list(seen.values())


class AccessibilityGravityWells:
    """Throttled OS Accessibility gravity-well prober and magnetic pull solver."""

    def __init__(
        self,
        *,
        enabled: bool = True,
        expansion: float = 2.6,
        strength: float = 0.35,
        velocity_threshold_px_s: float = 420.0,
        probe_hz: float = 40.0,
    ):
        self._lock = threading.RLock()
        self.enabled = bool(enabled)
        self.expansion = max(1.5, min(3.5, float(expansion)))
        self.strength = max(0.0, min(0.85, float(strength)))
        self.velocity_threshold_px_s = max(50.0, float(velocity_threshold_px_s))
        self.probe_interval = 1.0 / max(10.0, min(60.0, float(probe_hz)))
        self._last_probe_at = 0.0
        self._cached_targets: list[GravityTarget] = []
        self._active_role: str | None = None
        self._active_center: tuple[float, float] | None = None
        self._last_pos: tuple[float, float] | None = None
        self._last_ts: float | None = None

    def configure(
        self,
        *,
        enabled: bool | None = None,
        strength_pct: int | float | None = None,
        expansion: float | None = None,
    ) -> None:
        with self._lock:
            if enabled is not None:
                self.enabled = bool(enabled)
                if not self.enabled:
                    self._active_role = None
                    self._active_center = None
            if strength_pct is not None:
                self.strength = max(0.0, min(0.8, float(strength_pct) / 100.0))
            if expansion is not None:
                self.expansion = max(1.5, min(3.5, float(expansion)))

    def snapshot(self) -> dict:
        with self._lock:
            return {
                "gravity_well_active": bool(self.enabled and self._active_role is not None),
                "gravity_target_role": self._active_role if self.enabled else None,
                "gravity_target_center": list(self._active_center) if self._active_center else None,
            }

    def _refresh_targets_if_due(self, x: float, y: float, now: float) -> list[GravityTarget]:
        if now - self._last_probe_at < self.probe_interval:
            return self._cached_targets
        self._last_probe_at = now
        if sys.platform == "darwin":
            self._cached_targets = _macos_ax_probe(x, y)
        elif sys.platform.startswith("win"):
            self._cached_targets = _windows_uia_probe(x, y)
        else:
            self._cached_targets = []
        return self._cached_targets

    def apply_pull(
        self,
        x: float,
        y: float,
        now: float,
        *,
        targets: Iterable[GravityTarget] | None = None,
    ) -> tuple[float, float]:
        """Pull slowed pointer toward nearby interactive target center."""
        with self._lock:
            speed = 0.0
            if self._last_pos is not None and self._last_ts is not None:
                dt = now - self._last_ts
                if dt > 1e-4:
                    speed = math.hypot(x - self._last_pos[0], y - self._last_pos[1]) / dt
            self._last_pos = (x, y)
            self._last_ts = now

            if not self.enabled or self.strength <= 0.0:
                self._active_role = None
                self._active_center = None
                return (x, y)

            # High intentional sweep velocity suppresses gravity pull for free travel.
            if speed > self.velocity_threshold_px_s:
                self._active_role = None
                self._active_center = None
                return (x, y)

            candidate_list = list(targets) if targets is not None else self._refresh_targets_if_due(x, y, now)
            in_range = [t for t in candidate_list if t.expanded_contains(x, y, self.expansion)]
            if not in_range:
                self._active_role = None
                self._active_center = None
                return (x, y)

            nearest = min(in_range, key=lambda t: t.normalized_distance(x, y, self.expansion))
            cx, cy = nearest.center
            speed_factor = max(0.0, 1.0 - (speed / self.velocity_threshold_px_s))
            proximity = max(0.0, 1.0 - nearest.normalized_distance(x, y, self.expansion) * 0.45)
            alpha = max(0.0, min(0.85, self.strength * (0.45 + 0.55 * speed_factor) * proximity))

            self._active_role = nearest.role
            self._active_center = (round(cx, 1), round(cy, 1))
            return (x + alpha * (cx - x), y + alpha * (cy - y))
