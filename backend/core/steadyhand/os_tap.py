"""Low-level OS cursor interception using Quartz CGEventTap on macOS with pynput fallback."""

from __future__ import annotations

import sys
import threading
import time
from typing import Callable

# Callback signature: (event_kind, x, y, now) -> (out_x, out_y) | None
TapTransformCallback = Callable[[str, float, float, float], tuple[float, float] | None]


class SystemCursorInterceptor:
    """Intercepts raw OS pointer events in-place via Quartz CGEventTap or pynput fallback."""

    def __init__(self, on_event: TapTransformCallback):
        self._on_event = on_event
        self._lock = threading.RLock()
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._run_loop = None
        self._tap_port = None
        self._pynput_listener = None
        self._mode: str = "idle"
        self._last_error: str | None = None

    @property
    def active(self) -> bool:
        with self._lock:
            return self._mode in ("quartz_cgeventtap", "pynput_fallback")

    @property
    def mode(self) -> str:
        with self._lock:
            return self._mode

    @property
    def last_error(self) -> str | None:
        with self._lock:
            return self._last_error

    def start(self) -> tuple[bool, str | None]:
        with self._lock:
            if self.active:
                return True, None
            self._stop_event.clear()
            self._last_error = None

            if sys.platform == "darwin" and self._try_start_quartz_tap():
                return True, None

            return self._start_pynput_fallback()

    def stop(self) -> None:
        with self._lock:
            self._stop_event.set()
            if self._tap_port is not None:
                try:
                    import Quartz  # type: ignore[import-not-found]

                    Quartz.CGEventTapEnable(self._tap_port, False)
                    Quartz.CFMachPortInvalidate(self._tap_port)
                except Exception:
                    pass
                self._tap_port = None
            if self._run_loop is not None:
                try:
                    import Quartz  # type: ignore[import-not-found]

                    Quartz.CFRunLoopStop(self._run_loop)
                except Exception:
                    pass
                self._run_loop = None

            listener = self._pynput_listener
            self._pynput_listener = None
            if listener is not None:
                try:
                    listener.stop()
                except Exception:
                    pass
            thread = self._thread
            self._thread = None
            self._mode = "idle"

        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=1.5)

    def _try_start_quartz_tap(self) -> bool:
        try:
            import Quartz  # type: ignore[import-not-found]
        except Exception:
            return False

        try:
            import ApplicationServices as AS  # type: ignore[import-not-found]

            if hasattr(AS, "AXIsProcessTrusted") and not AS.AXIsProcessTrusted():
                self._last_error = (
                    "macOS Accessibility permission required for CGEventTap; using pynput fallback."
                )
                return False
        except Exception:
            pass

        ready = threading.Event()
        started_ok = {"ok": False}
        tap_box: dict[str, object] = {"tap": None, "loop": None}

        def _tap_thread() -> None:
            mask = (
                (1 << Quartz.kCGEventMouseMoved)
                | (1 << Quartz.kCGEventLeftMouseDragged)
                | (1 << Quartz.kCGEventLeftMouseDown)
                | (1 << Quartz.kCGEventLeftMouseUp)
            )

            def _callback(_proxy, event_type, event, _refcon):
                if event_type in (
                    Quartz.kCGEventTapDisabledByTimeout,
                    Quartz.kCGEventTapDisabledByUserInput,
                ):
                    if tap_box["tap"] is not None:
                        Quartz.CGEventTapEnable(tap_box["tap"], True)
                    return event

                if event_type == Quartz.kCGEventLeftMouseDown:
                    kind = "down"
                elif event_type == Quartz.kCGEventLeftMouseUp:
                    kind = "up"
                elif event_type in (Quartz.kCGEventMouseMoved, Quartz.kCGEventLeftMouseDragged):
                    kind = "move"
                else:
                    return event

                try:
                    pt = Quartz.CGEventGetLocation(event)
                    transformed = self._on_event(kind, float(pt.x), float(pt.y), time.perf_counter())
                    if transformed is not None:
                        new_pt = Quartz.CGPoint(float(transformed[0]), float(transformed[1]))
                        Quartz.CGEventSetLocation(event, new_pt)
                except Exception:
                    return event
                return event

            tap = Quartz.CGEventTapCreate(
                Quartz.kCGHIDEventTap,
                Quartz.kCGHeadInsertEventTap,
                Quartz.kCGEventTapOptionDefault,
                mask,
                _callback,
                None,
            )
            if tap is None:
                ready.set()
                return

            source = Quartz.CFMachPortCreateRunLoopSource(None, tap, 0)
            loop = Quartz.CFRunLoopGetCurrent()
            tap_box["tap"] = tap
            tap_box["loop"] = loop
            Quartz.CFRunLoopAddSource(loop, source, Quartz.kCFRunLoopCommonModes)
            Quartz.CGEventTapEnable(tap, True)
            started_ok["ok"] = True
            ready.set()
            Quartz.CFRunLoopRun()

        thread = threading.Thread(target=_tap_thread, name="truecursor-cgeventtap", daemon=True)
        thread.start()
        ready.wait(timeout=1.0)
        if not started_ok["ok"]:
            self._last_error = (
                "Could not create macOS CGEventTap; grant Accessibility & Input Monitoring in System Settings."
            )
            return False

        self._tap_port = tap_box["tap"]
        self._run_loop = tap_box["loop"]
        self._thread = thread
        self._mode = "quartz_cgeventtap"
        return True

    def _start_pynput_fallback(self) -> tuple[bool, str | None]:
        try:
            from pynput import mouse

            def on_move(x: float, y: float) -> None:
                self._on_event("move", float(x), float(y), time.perf_counter())

            def on_click(x: float, y: float, button, pressed: bool) -> None:
                if getattr(button, "name", "") == "left":
                    self._on_event("down" if pressed else "up", float(x), float(y), time.perf_counter())

            listener = mouse.Listener(on_move=on_move, on_click=on_click)
            listener.daemon = True
            listener.start()
            self._pynput_listener = listener
            self._mode = "pynput_fallback"
            return True, self._last_error
        except Exception as exc:
            self._last_error = str(exc)
            self._mode = "idle"
            return False, self._last_error
