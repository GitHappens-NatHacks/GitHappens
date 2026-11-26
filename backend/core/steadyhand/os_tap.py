"""Low-level OS cursor interception using Quartz CGEventTap (macOS) or WH_MOUSE_LL (Windows)."""

from __future__ import annotations

import ctypes
import sys
import threading
import time
from typing import Any, Callable

# Callback signature: (event_kind, x, y, now) -> (out_x, out_y) | "suppress" | None
TapTransformCallback = Callable[[str, float, float, float], tuple[float, float] | str | None]


class SystemCursorInterceptor:
    """Intercepts raw OS pointer events in-place via Quartz, Win32 WH_MOUSE_LL, or pynput."""

    def __init__(self, on_event: TapTransformCallback, *, handle_extended_events: bool = False):
        self._on_event = on_event
        self._handle_extended_events = bool(handle_extended_events)
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
        self._local = threading.local()

    @property
    def current_event_info(self) -> dict[str, Any]:
        """Per-thread metadata for the event currently being processed by the callback."""
        info = getattr(self._local, "event_info", None)
        if isinstance(info, dict):
            return info
        return {}

    def _set_event_info(self, info: dict[str, Any]) -> None:
        self._local.event_info = info

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

        def _quartz_modifiers(event) -> set[str]:
            mods: set[str] = set()
            get_flags = getattr(Quartz, "CGEventGetFlags", None)
            if not callable(get_flags):
                return mods
            try:
                flags = int(get_flags(event))
            except Exception:
                return mods
            if flags & int(getattr(Quartz, "kCGEventFlagMaskAlternate", 0)):
                mods.add("alt")
            if flags & int(getattr(Quartz, "kCGEventFlagMaskShift", 0)):
                mods.add("shift")
            if flags & int(getattr(Quartz, "kCGEventFlagMaskControl", 0)):
                mods.add("ctrl")
            if flags & int(getattr(Quartz, "kCGEventFlagMaskSecondaryFn", 0)):
                mods.add("fn")
            return mods

        def _tap_thread() -> None:
            mask = (
                (1 << Quartz.kCGEventMouseMoved)
                | (1 << Quartz.kCGEventLeftMouseDragged)
                | (1 << Quartz.kCGEventLeftMouseDown)
                | (1 << Quartz.kCGEventLeftMouseUp)
            )
            if self._handle_extended_events:
                for extra_name in (
                    "kCGEventRightMouseDown",
                    "kCGEventRightMouseUp",
                    "kCGEventRightMouseDragged",
                    "kCGEventOtherMouseDown",
                    "kCGEventOtherMouseUp",
                    "kCGEventOtherMouseDragged",
                    "kCGEventScrollWheel",
                ):
                    val = getattr(Quartz, extra_name, None)
                    if isinstance(val, int):
                        mask |= 1 << val

            right_down = getattr(Quartz, "kCGEventRightMouseDown", None)
            right_up = getattr(Quartz, "kCGEventRightMouseUp", None)
            right_drag = getattr(Quartz, "kCGEventRightMouseDragged", None)
            other_down = getattr(Quartz, "kCGEventOtherMouseDown", None)
            other_up = getattr(Quartz, "kCGEventOtherMouseUp", None)
            other_drag = getattr(Quartz, "kCGEventOtherMouseDragged", None)
            scroll_ev = getattr(Quartz, "kCGEventScrollWheel", None)

            get_int_field = getattr(Quartz, "CGEventGetIntegerValueField", None)
            set_int_field = getattr(Quartz, "CGEventSetIntegerValueField", None)
            delta_x_field = getattr(Quartz, "kCGMouseEventDeltaX", None)
            delta_y_field = getattr(Quartz, "kCGMouseEventDeltaY", None)
            scroll_axis1 = getattr(Quartz, "kCGScrollWheelEventDeltaAxis1", None)

            def _callback(_proxy, event_type, event, _refcon):
                if event_type in (
                    Quartz.kCGEventTapDisabledByTimeout,
                    Quartz.kCGEventTapDisabledByUserInput,
                ):
                    if tap_box["tap"] is not None:
                        Quartz.CGEventTapEnable(tap_box["tap"], True)
                    return event

                button = "left"
                if event_type == Quartz.kCGEventLeftMouseDown:
                    kind = "down"
                elif event_type == Quartz.kCGEventLeftMouseUp:
                    kind = "up"
                elif event_type in (Quartz.kCGEventMouseMoved, Quartz.kCGEventLeftMouseDragged):
                    kind = "move"
                elif self._handle_extended_events and event_type == right_down:
                    kind = "down"
                    button = "right"
                elif self._handle_extended_events and event_type == right_up:
                    kind = "up"
                    button = "right"
                elif self._handle_extended_events and event_type == right_drag:
                    kind = "move"
                    button = "right"
                elif self._handle_extended_events and event_type == other_down:
                    kind = "down"
                    button = "other"
                elif self._handle_extended_events and event_type == other_up:
                    kind = "up"
                    button = "other"
                elif self._handle_extended_events and event_type == other_drag:
                    kind = "move"
                    button = "other"
                elif self._handle_extended_events and event_type == scroll_ev:
                    kind = "scroll"
                else:
                    return event

                try:
                    pt = Quartz.CGEventGetLocation(event)
                    raw_dx = 0.0
                    raw_dy = 0.0
                    scroll_dy = 0.0
                    if callable(get_int_field):
                        if delta_x_field is not None and delta_y_field is not None:
                            raw_dx = float(get_int_field(event, delta_x_field))
                            raw_dy = float(get_int_field(event, delta_y_field))
                        if kind == "scroll" and scroll_axis1 is not None:
                            scroll_dy = float(get_int_field(event, scroll_axis1))

                    self._set_event_info(
                        {
                            "button": button,
                            "dx": raw_dx,
                            "dy": raw_dy,
                            "has_delta": bool(raw_dx != 0.0 or raw_dy != 0.0),
                            "scroll_dy": scroll_dy,
                            "modifiers": _quartz_modifiers(event),
                        }
                    )
                    transformed = self._on_event(kind, float(pt.x), float(pt.y), time.perf_counter())
                    if transformed == "suppress":
                        return None
                    if isinstance(transformed, tuple):
                        nx, ny = float(transformed[0]), float(transformed[1])
                        new_pt = Quartz.CGPoint(nx, ny)
                        Quartz.CGEventSetLocation(event, new_pt)
                        if (
                            kind == "move"
                            and callable(set_int_field)
                            and delta_x_field is not None
                            and delta_y_field is not None
                        ):
                            adj_dx = round(nx - float(pt.x) + raw_dx)
                            adj_dy = round(ny - float(pt.y) + raw_dy)
                            set_int_field(event, delta_x_field, int(adj_dx))
                            set_int_field(event, delta_y_field, int(adj_dy))
                except Exception:
                    return event
                finally:
                    self._set_event_info({})
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

        thread = threading.Thread(target=_tap_thread, name="clearcursor-cgeventtap", daemon=True)
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
        WM_RBUTTONDOWN = 0x0204
        WM_RBUTTONUP = 0x0205
        WM_MBUTTONDOWN = 0x0207
        WM_MBUTTONUP = 0x0208
        WM_MOUSEWHEEL = 0x020A
        LLMHF_INJECTED = 0x00000001

        VK_SHIFT = 0x10
        VK_CONTROL = 0x11
        VK_MENU = 0x12

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
        get_key_state = getattr(user32, "GetAsyncKeyState", None)

        def _win_modifiers() -> set[str]:
            mods: set[str] = set()
            if not callable(get_key_state):
                return mods
            try:
                if int(get_key_state(VK_MENU)) & 0x8000:
                    mods.add("alt")
                if int(get_key_state(VK_SHIFT)) & 0x8000:
                    mods.add("shift")
                if int(get_key_state(VK_CONTROL)) & 0x8000:
                    mods.add("ctrl")
            except Exception:
                pass
            return mods

        def _win_thread() -> None:
            def _proc(n_code: int, w_param: int, l_param: int) -> int:
                if n_code >= 0 and l_param:
                    info = ctypes.cast(l_param, ctypes.POINTER(_MSLLHOOKSTRUCT)).contents
                    # Never re-process SetCursorPos or synthetic clicks injected by ClearCursor.
                    if not (info.flags & LLMHF_INJECTED):
                        kind = None
                        button = "left"
                        scroll_dy = 0.0
                        if w_param == WM_MOUSEMOVE:
                            kind = "move"
                        elif w_param == WM_LBUTTONDOWN:
                            kind = "down"
                        elif w_param == WM_LBUTTONUP:
                            kind = "up"
                        elif self._handle_extended_events and w_param == WM_RBUTTONDOWN:
                            kind = "down"
                            button = "right"
                        elif self._handle_extended_events and w_param == WM_RBUTTONUP:
                            kind = "up"
                            button = "right"
                        elif self._handle_extended_events and w_param == WM_MBUTTONDOWN:
                            kind = "down"
                            button = "other"
                        elif self._handle_extended_events and w_param == WM_MBUTTONUP:
                            kind = "up"
                            button = "other"
                        elif self._handle_extended_events and w_param == WM_MOUSEWHEEL:
                            kind = "scroll"
                            raw_wheel = ctypes.c_short((info.mouseData >> 16) & 0xFFFF).value
                            scroll_dy = float(raw_wheel) / 120.0

                        if kind is not None:
                            try:
                                self._set_event_info(
                                    {
                                        "button": button,
                                        "dx": 0.0,
                                        "dy": 0.0,
                                        "has_delta": False,
                                        "scroll_dy": scroll_dy,
                                        "modifiers": _win_modifiers(),
                                    }
                                )
                                out = self._on_event(
                                    kind, float(info.pt.x), float(info.pt.y), time.perf_counter()
                                )
                                if out == "suppress":
                                    return 1
                                if isinstance(out, tuple):
                                    nx, ny = round(out[0]), round(out[1])
                                    user32.SetCursorPos(nx, ny)
                                    if kind == "move":
                                        return 1
                            except Exception:
                                pass
                            finally:
                                self._set_event_info({})
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

        thread = threading.Thread(target=_win_thread, name="clearcursor-win32-hook", daemon=True)
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
                self._set_event_info({"button": "left", "dx": 0.0, "dy": 0.0, "has_delta": False, "scroll_dy": 0.0, "modifiers": set()})
                try:
                    self._on_event("move", float(x), float(y), time.perf_counter())
                finally:
                    self._set_event_info({})

            def on_click(x: float, y: float, button, pressed: bool) -> None:
                btn_name = getattr(button, "name", "")
                mapped = "left" if btn_name == "left" else "right" if btn_name == "right" else "other"
                if mapped == "left" or self._handle_extended_events:
                    self._set_event_info({"button": mapped, "dx": 0.0, "dy": 0.0, "has_delta": False, "scroll_dy": 0.0, "modifiers": set()})
                    try:
                        self._on_event("down" if pressed else "up", float(x), float(y), time.perf_counter())
                    finally:
                        self._set_event_info({})

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
