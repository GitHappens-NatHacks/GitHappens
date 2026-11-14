"""Multi-monitor virtual screen geometry, DPI scale, and refresh-rate helpers.

Supports macOS (Quartz CoreGraphics) and Windows (Per-Monitor DPI Awareness v2
plus EnumDisplayMonitors), with deterministic fallbacks when headless.
"""

from __future__ import annotations

import ctypes
import sys
from dataclasses import dataclass

from backend.core.gaze.controller import ScreenRect


@dataclass(frozen=True)
class DisplayInfo:
    """Normalized descriptor for a physical or virtual monitor."""

    id: str
    left: int
    top: int
    width: int
    height: int
    scale_factor: float = 1.0
    refresh_hz: float = 60.0
    is_primary: bool = True

    @property
    def right(self) -> int:
        return self.left + self.width

    @property
    def bottom(self) -> int:
        return self.top + self.height

    def contains(self, x: float, y: float) -> bool:
        return self.left <= x < self.right and self.top <= y < self.bottom

    def as_dict(self) -> dict:
        return {
            "id": self.id,
            "left": self.left,
            "top": self.top,
            "width": self.width,
            "height": self.height,
            "scale_factor": round(self.scale_factor, 3),
            "refresh_hz": round(self.refresh_hz, 2),
            "is_primary": self.is_primary,
        }


def enable_windows_dpi_awareness() -> bool:
    """Opt Windows process into Per-Monitor v2 DPI coordinates when supported."""
    if not sys.platform.startswith("win"):
        return False
    try:
        user32 = ctypes.windll.user32
        # DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2 = -4
        if hasattr(user32, "SetProcessDpiAwarenessContext"):
            if user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4)):
                return True
        shcore = getattr(ctypes.windll, "shcore", None)
        if shcore is not None and hasattr(shcore, "SetProcessDpiAwareness"):
            shcore.SetProcessDpiAwareness(2)
            return True
    except Exception:
        return False
    return False


def _macos_displays() -> list[DisplayInfo]:
    try:
        import Quartz  # type: ignore[import-not-found]
    except Exception:
        return []

    try:
        err, ids, count = Quartz.CGGetActiveDisplayList(16, None, None)
        if err != 0 or not ids or count <= 0:
            return []
        main_id = Quartz.CGMainDisplayID()
        out: list[DisplayInfo] = []
        for idx, did in enumerate(ids[:count]):
            bounds = Quartz.CGDisplayBounds(did)
            width = max(1, int(round(bounds.size.width)))
            height = max(1, int(round(bounds.size.height)))
            left = int(round(bounds.origin.x))
            top = int(round(bounds.origin.y))

            scale = 1.0
            refresh = 60.0
            mode = Quartz.CGDisplayCopyDisplayMode(did)
            if mode is not None:
                px_w = float(Quartz.CGDisplayModeGetPixelWidth(mode) or width)
                if width > 0 and px_w > 0:
                    scale = max(1.0, px_w / float(width))
                hz = float(Quartz.CGDisplayModeGetRefreshRate(mode) or 0.0)
                if hz > 10.0:
                    refresh = hz

            out.append(
                DisplayInfo(
                    id=f"display-{int(did)}",
                    left=left,
                    top=top,
                    width=width,
                    height=height,
                    scale_factor=scale,
                    refresh_hz=refresh,
                    is_primary=(did == main_id or idx == 0),
                )
            )
        return out
    except Exception:
        return []


def _windows_displays() -> list[DisplayInfo]:
    if not sys.platform.startswith("win"):
        return []
    enable_windows_dpi_awareness()
    try:
        user32 = ctypes.windll.user32
        shcore = getattr(ctypes.windll, "shcore", None)
    except Exception:
        return []

    class _RECT(ctypes.Structure):
        _fields_ = [
            ("left", ctypes.c_long),
            ("top", ctypes.c_long),
            ("right", ctypes.c_long),
            ("bottom", ctypes.c_long),
        ]

    displays: list[DisplayInfo] = []
    win_functype = getattr(ctypes, "WINFUNCTYPE", ctypes.CFUNCTYPE)
    MONITORENUMPROC = win_functype(
        ctypes.c_int,
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.POINTER(_RECT),
        ctypes.c_ssize_t,
    )

    def _callback(hmon, _hdc, rect_ptr, _lparam):
        rect = rect_ptr.contents
        w = max(1, int(rect.right - rect.left))
        h = max(1, int(rect.bottom - rect.top))
        scale = 1.0
        if shcore is not None and hasattr(shcore, "GetDpiForMonitor"):
            dpi_x = ctypes.c_uint()
            dpi_y = ctypes.c_uint()
            # MDT_EFFECTIVE_DPI = 0
            if shcore.GetDpiForMonitor(hmon, 0, ctypes.byref(dpi_x), ctypes.byref(dpi_y)) == 0:
                if dpi_x.value > 0:
                    scale = float(dpi_x.value) / 96.0

        displays.append(
            DisplayInfo(
                id=f"win-monitor-{len(displays)}",
                left=int(rect.left),
                top=int(rect.top),
                width=w,
                height=h,
                scale_factor=scale,
                refresh_hz=60.0,
                is_primary=(rect.left == 0 and rect.top == 0),
            )
        )
        return 1

    try:
        user32.EnumDisplayMonitors(0, 0, MONITORENUMPROC(_callback), 0)
    except Exception:
        return []
    return displays


def detect_displays(fallback_width: int = 1440, fallback_height: int = 900) -> list[DisplayInfo]:
    """Return active displays across macOS/Windows, or a single primary fallback."""
    detected: list[DisplayInfo] = []
    if sys.platform == "darwin":
        detected = _macos_displays()
    elif sys.platform.startswith("win"):
        detected = _windows_displays()

    if detected:
        return detected
    return [
        DisplayInfo(
            id="primary-default",
            left=0,
            top=0,
            width=max(320, int(fallback_width)),
            height=max(240, int(fallback_height)),
            scale_factor=1.0,
            refresh_hz=60.0,
            is_primary=True,
        )
    ]


def virtual_screen_rect(
    displays: list[DisplayInfo] | None = None,
    *,
    fallback_width: int = 1440,
    fallback_height: int = 900,
) -> ScreenRect:
    """Compute the combined bounding rectangle across all active displays."""
    items = displays if displays else detect_displays(fallback_width, fallback_height)
    left = min(d.left for d in items)
    top = min(d.top for d in items)
    right = max(d.right for d in items)
    bottom = max(d.bottom for d in items)
    return ScreenRect(left=left, top=top, width=max(1, right - left), height=max(1, bottom - top))


def display_for_point(
    x: float,
    y: float,
    displays: list[DisplayInfo] | None = None,
) -> DisplayInfo:
    """Return the monitor containing (x, y), falling back to primary or nearest monitor."""
    items = displays if displays else detect_displays()
    for d in items:
        if d.contains(x, y):
            return d
    for d in items:
        if d.is_primary:
            return d
    return items[0]
