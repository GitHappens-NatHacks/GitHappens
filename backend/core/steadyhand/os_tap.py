"""Low-level OS cursor interception using Quartz CGEventTap (macOS) or WH_MOUSE_LL (Windows)."""

from __future__ import annotations

import ctypes
import sys
import threading
import time
from typing import Callable

# Callback signature: (event_kind, x, y, now) -> (out_x, out_y) | None
TapTransformCallback = Callable[[str, float, float, float], tuple[float, float] | None]


class SystemCursorInterceptor:
    """Intercepts raw OS pointer events in-place via Quartz, Win32 WH_MOUSE_LL, or pynput."""

    def __init__(self, on_event: TapTransformCallback):
        self._on_event = on_event
        self._lock = threading.RLock()
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._run_loop = None
        self._tap_port = None
        self._win_hook = None
        self._win_thread_id: int | None = None
        self._pynput_listener = None
        self._mode: str = "idle"
        self._last_error: str | None = None

    @property
    def active(self) -> bool:
        with self._lock:
            return self._mode in ("quartz_cgeventtap", "win32_wh_mouse_ll", "pynput_fallback")

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
            if sys.platform.startswith("win") and self._try_start_win32_hook():
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

            if self._win_hook is not None:
                try:
                    user32 = ctypes.windll.user32
                    user32.UnhookWindowsHookEx(self._win_hook)
                    if self._win_thread_id:
                        # WM_QUIT = 0x0012
                        user32.PostThreadMessageW(self._win_thread_id, 0x0012, 0, 0)
                except Exception:
                    pass
                self._win_hook = None
                self._win_thread_id = None

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

    def _try_start_win32_hook(self) -> bool:
        """Install Windows WH_MOUSE_LL low-level mouse hook with SetCursorPos smoothing."""
        windll = getattr(ctypes, "windll", None)
        if windll is None:
            return False
        user32 = getattr(windll, "user32", None)
        kernel32 = getattr(windll, "kernel32", None)
        if user32 is None or kernel32 is None:
            return False

        from backend.core.steadyhand.displays import enable_windows_dpi_awareness

        enable_windows_dpi_awareness()

        WH_MOUSE_LL = 14
        WM_MOUSEMOVE = 0x0200
        WM_LBUTTONDOWN = 0x0201
        WM_LBUTTONUP = 0x0202
        LLMHF_INJECTED = 0x00000001

        class _POINT(ctypes.Structure):
            _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

        class _MSLLHOOKSTRUCT(ctypes.Structure):
            _fields_ = [
                ("pt", _POINT),
                ("mouseData", ctypes.c_ulong),
                ("flags", ctypes.c_ulong),
                ("time", ctypes.c_ulong),
                ("dwExtraInfo", ctypes.c_size_t),
            ]

        class _MSG(ctypes.Structure):
            _fields_ = [
                ("hwnd", ctypes.c_void_p),
                ("message", ctypes.c_uint),
                ("wParam", ctypes.c_size_t),
                ("lParam", ctypes.c_ssize_t),
                ("time", ctypes.c_ulong),
                ("pt", _POINT),
            ]

        ready = threading.Event()
        hook_box: dict[str, object] = {"ok": False, "hook": None, "tid": None}

        win_functype = getattr(ctypes, "WINFUNCTYPE", ctypes.CFUNCTYPE)
        HOOKPROC = win_functype(ctypes.c_ssize_t, ctypes.c_int, ctypes.c_size_t, ctypes.c_ssize_t)

        def _win_thread() -> None:
            def _proc(n_code: int, w_param: int, l_param: int) -> int:
                if n_code >= 0 and l_param:
                    info = ctypes.cast(l_param, ctypes.POINTER(_MSLLHOOKSTRUCT)).contents
                    # Never re-process SetCursorPos or synthetic clicks injected by TrueCursor.
                    if not (info.flags & LLMHF_INJECTED):
                        kind = None
                        if w_param == WM_MOUSEMOVE:
                            kind = "move"
                        elif w_param == WM_LBUTTONDOWN:
                            kind = "down"
                        elif w_param == WM_LBUTTONUP:
                            kind = "up"

                        if kind is not None:
                            try:
                                out = self._on_event(
                                    kind, float(info.pt.x), float(info.pt.y), time.perf_counter()
                                )
                                if out is not None:
                                    nx, ny = round(out[0]), round(out[1])
                                    user32.SetCursorPos(nx, ny)
                                    if kind == "move":
                                        return 1
                            except Exception:
                                pass
                return int(user32.CallNextHookEx(None, n_code, w_param, l_param))

            callback = HOOKPROC(_proc)
            hook = user32.SetWindowsHookExW(WH_MOUSE_LL, callback, kernel32.GetModuleHandleW(None), 0)
            if not hook:
                ready.set()
                return

            hook_box["hook"] = hook
            hook_box["tid"] = int(kernel32.GetCurrentThreadId())
            hook_box["ok"] = True
            # Keep ctypes callback alive for the duration of the message pump.
            hook_box["cb"] = callback
            ready.set()

            msg = _MSG()
            while not self._stop_event.is_set():
                res = user32.GetMessageW(ctypes.byref(msg), 0, 0, 0)
                if res <= 0:
                    break
                user32.TranslateMessage(ctypes.byref(msg))
                user32.DispatchMessageW(ctypes.byref(msg))

        thread = threading.Thread(target=_win_thread, name="truecursor-win32-hook", daemon=True)
        thread.start()
        ready.wait(timeout=1.0)
        if not hook_box["ok"]:
            self._last_error = "Could not install Windows WH_MOUSE_LL hook; using pynput fallback."
            return False

        self._win_hook = hook_box["hook"]
        self._win_thread_id = hook_box["tid"]  # type: ignore[assignment]
        self._thread = thread
        self._mode = "win32_wh_mouse_ll"
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
