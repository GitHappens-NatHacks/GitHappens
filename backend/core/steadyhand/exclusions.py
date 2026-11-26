"""Per-application exclusion monitor for automatic bypass in creative/gaming apps."""

from __future__ import annotations

import ctypes
import sys
import threading
import time


def _get_frontmost_app_macos() -> str | None:
    try:
        from AppKit import NSWorkspace  # type: ignore[import-not-found]

        app = NSWorkspace.sharedWorkspace().frontmostApplication()
        if app is None:
            return None
        name = app.localizedName() or ""
        bundle = app.bundleIdentifier() or ""
        combined = " ".join(part for part in (str(name), str(bundle)) if part)
        return combined or None
    except Exception:
        return None


def _get_frontmost_app_windows() -> str | None:
    try:
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            return None
        pid = ctypes.c_ulong()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if not pid.value:
            return None
        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid.value)
        if not handle:
            return None
        try:
            buf = ctypes.create_unicode_buffer(512)
            size = ctypes.c_ulong(len(buf))
            if kernel32.QueryFullProcessImageNameW(handle, 0, buf, ctypes.byref(size)):
                full_path = buf.value
                return full_path.rsplit("\\", 1)[-1] or None
        finally:
            kernel32.CloseHandle(handle)
    except Exception:
        return None
    return None


def detect_frontmost_app() -> str | None:
    """Return the active foreground application name/identifier, or None if unavailable."""
    if sys.platform == "darwin":
        return _get_frontmost_app_macos()
    if sys.platform.startswith("win"):
        return _get_frontmost_app_windows()
    return None


def match_excluded_app(active_app: str | None, excluded_apps: list[str] | tuple[str, ...]) -> str | None:
    """Return the matching exclusion pattern if `active_app` matches any excluded rule."""
    if not active_app or not excluded_apps:
        return None
    haystack = active_app.strip().lower()
    if not haystack:
        return None
    for rule in excluded_apps:
        needle = str(rule).strip().lower()
        if needle and needle in haystack:
            return str(rule).strip()
    return None


class ActiveAppMonitor:
    """Background 2 Hz foreground-app watcher for zero-latency exclusion checks."""

    def __init__(self, poll_hz: float = 2.0):
        self._lock = threading.RLock()
        self._poll_interval = 1.0 / max(0.5, min(10.0, float(poll_hz)))
        self._excluded_apps: list[str] = []
        self._active_app: str | None = None
        self._matched_rule: str | None = None
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    @property
    def excluded_apps(self) -> list[str]:
        with self._lock:
            return list(self._excluded_apps)

    @property
    def matched_rule(self) -> str | None:
        with self._lock:
            return self._matched_rule

    @property
    def active_app(self) -> str | None:
        with self._lock:
            return self._active_app

    def set_excluded_apps(self, apps: list[str] | tuple[str, ...]) -> None:
        cleaned = [str(a).strip() for a in apps if str(a).strip()]
        with self._lock:
            self._excluded_apps = cleaned
            if not cleaned:
                self._matched_rule = None
                self.stop()
            else:
                self._matched_rule = match_excluded_app(self._active_app, cleaned)
                if self._thread is None or not self._thread.is_alive():
                    self.start()

    def update_active_app(self, app_name: str | None) -> str | None:
        """Manually update active app (useful for tests and direct probes)."""
        with self._lock:
            self._active_app = app_name
            self._matched_rule = match_excluded_app(app_name, self._excluded_apps)
            return self._matched_rule

    def start(self) -> None:
        with self._lock:
            if not self._excluded_apps:
                return
            if self._thread is not None and self._thread.is_alive():
                return
            self._stop_event.clear()
            self._thread = threading.Thread(
                target=self._run,
                name="clearcursor-app-monitor",
                daemon=True,
            )
            self._thread.start()

    def stop(self, timeout: float = 1.0) -> None:
        self._stop_event.set()
        with self._lock:
            thread = self._thread
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=timeout)
        with self._lock:
            if self._thread is thread and (thread is None or not thread.is_alive()):
                self._thread = None

    def _run(self) -> None:
        while not self._stop_event.is_set():
            with self._lock:
                has_rules = bool(self._excluded_apps)
            if has_rules:
                name = detect_frontmost_app()
                self.update_active_app(name)
            self._stop_event.wait(self._poll_interval)
