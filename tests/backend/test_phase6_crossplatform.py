"""Phase 6 tests: Windows hooks/UIA, macOS Accessibility prompts, multi-monitor DPI, and webcam lighting."""

from __future__ import annotations

import ctypes
import sys
from types import SimpleNamespace

import numpy as np
from fastapi.testclient import TestClient

from backend.api.main import create_app
from backend.core.gaze.calibration import GazeCalibration
from backend.core.gaze.controller import GazeController, ScreenRect
from backend.core.gaze.tracker import normalize_frame_lighting
from backend.core.steadyhand.displays import (
    DisplayInfo,
    display_for_point,
    virtual_screen_rect,
)
from backend.core.steadyhand.gravity_wells import _windows_uia_probe
from backend.core.steadyhand.os_tap import SystemCursorInterceptor
from backend.core.steadyhand.permissions import get_system_permissions
from backend.db.database import Database


def test_permissions_macos_prompt_and_windows_readiness(monkeypatch):
    prompt_calls: list[dict] = []
    request_listen_calls: list[bool] = []

    class _FakeAS:
        @staticmethod
        def AXIsProcessTrusted():
            return False

        @staticmethod
        def AXIsProcessTrustedWithOptions(opts):
            prompt_calls.append(dict(opts))
            return False

    class _FakeQuartz:
        @staticmethod
        def CGPreflightListenEventAccess():
            return True

        @staticmethod
        def CGRequestListenEventAccess():
            request_listen_calls.append(True)
            return False

    monkeypatch.setattr(sys, "platform", "darwin")
    monkeypatch.setitem(sys.modules, "ApplicationServices", _FakeAS)
    monkeypatch.setitem(sys.modules, "Quartz", _FakeQuartz)

    passive = get_system_permissions(prompt=False)
    assert passive["platform"] == "macos"
    assert passive["accessibility_trusted"] is False
    assert passive["needs_prompt"] is True
    assert prompt_calls == []

    active = get_system_permissions(prompt=True)
    assert prompt_calls == [{"AXTrustedCheckOptionPrompt": True}]
    assert request_listen_calls == [True]
    assert active["needs_prompt"] is True

    monkeypatch.setattr(sys, "platform", "win32")
    win_perms = get_system_permissions(prompt=False)
    assert win_perms["platform"] == "windows"
    assert win_perms["needs_prompt"] is False
    assert "WH_MOUSE_LL" in (win_perms["message"] or "")


def test_api_system_permissions_and_displays_endpoints(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "backend.api.routes.get_system_permissions",
        lambda prompt=False: {
            "platform": "macos",
            "accessibility_trusted": bool(prompt),
            "input_monitoring_trusted": True,
            "needs_prompt": not bool(prompt),
            "message": None if prompt else "Grant Accessibility access.",
        },
    )
    opened_targets: list[str] = []
    monkeypatch.setattr(
        "backend.api.routes.open_permission_settings",
        lambda target="accessibility": opened_targets.append(target) or True,
    )

    app = create_app(db_path=tmp_path / "sys.db", auto_start_workers=False)
    with TestClient(app) as client:
        r1 = client.get("/api/system/permissions")
        assert r1.status_code == 200
        assert r1.json()["needs_prompt"] is True

        r2 = client.post(
            "/api/system/permissions/prompt",
            json={"target": "accessibility", "open_settings": True},
        )
        assert r2.status_code == 200
        assert r2.json()["settings_opened"] is True
        assert opened_targets == ["accessibility"]

        r3 = client.get("/api/system/displays")
        assert r3.status_code == 200
        data = r3.json()
        assert data["virtual_rect"]["width"] >= 320
        assert len(data["displays"]) >= 1


def test_multi_monitor_virtual_screen_rect_and_gaze_clamping():
    left_ext = DisplayInfo(
        id="ext-left",
        left=-1920,
        top=-120,
        width=1920,
        height=1080,
        scale_factor=1.0,
        refresh_hz=144.0,
        is_primary=False,
    )
    primary = DisplayInfo(
        id="primary",
        left=0,
        top=0,
        width=2560,
        height=1440,
        scale_factor=2.0,
        refresh_hz=120.0,
        is_primary=True,
    )
    vrect = virtual_screen_rect([left_ext, primary])
    assert vrect == ScreenRect(left=-1920, top=-120, width=4480, height=1560)
    assert display_for_point(-600, 200, [left_ext, primary]).id == "ext-left"
    assert display_for_point(800, 400, [left_ext, primary]).id == "primary"

    points: list[tuple[int, int]] = []
    ctrl = GazeController(screen_rect=vrect, on_point=points.append)
    cal = GazeCalibration()
    # Direct identity mapping in normalized monitor space (-1500 -> left monitor)
    cal.fit([(0.0, 0.0), (1.0, 0.0), (0.0, 1.0), (1.0, 1.0)], [(-1500.0, 100.0), (1500.0, 100.0), (-1500.0, 900.0), (1500.0, 900.0)])
    ctrl.set_calibration(cal, 20.0)
    ctrl.process({"face": True, "feature": (0.0, 0.2), "ear": 0.3, "ts_ms": 1000})
    assert points
    assert points[-1][0] < 0  # Negative X on external monitor is preserved, not clamped to 0!


def test_webcam_lighting_normalization_low_light_backlit_and_overexposed():
    normal = np.full((120, 160, 3), 125, dtype=np.uint8)
    out_norm, q_norm, luma_norm = normalize_frame_lighting(normal)
    assert q_norm == "ok"
    assert 115 <= luma_norm <= 135
    assert out_norm.shape == normal.shape

    # Dark frame with textured face detail inside center
    dark = np.full((120, 160, 3), 24, dtype=np.uint8)
    dark[30:90, 40:120] = 48
    out_dark, q_dark, luma_dark = normalize_frame_lighting(dark)
    assert q_dark == "low_light"
    assert luma_dark < 68.0
    assert float(np.mean(out_dark[30:90, 40:120])) > float(np.mean(dark[30:90, 40:120]))

    # Backlit: very bright border (230), dim center subject (55)
    backlit = np.full((120, 160, 3), 230, dtype=np.uint8)
    backlit[30:90, 40:120] = 55
    backlit[45:75, 55:105] = 70
    out_back, q_back, _ = normalize_frame_lighting(backlit)
    assert q_back == "backlit"
    assert np.std(out_back[30:90, 40:120]) >= np.std(backlit[30:90, 40:120])

    bright = np.full((120, 160, 3), 240, dtype=np.uint8)
    _, q_bright, _ = normalize_frame_lighting(bright)
    assert q_bright == "overexposed"


def test_win32_wh_mouse_ll_and_windows_uia_probe_lifecycle(monkeypatch):
    hook_calls: dict[str, object] = {"unhooked": False, "posted_quit": False}
    fake_hook_handle = 123456

    class _FakeUser32:
        @staticmethod
        def SetProcessDpiAwarenessContext(_ctx):
            return 1

        @staticmethod
        def SetWindowsHookExW(_hook_id, cb, _mod, _tid):
            hook_calls["cb"] = cb
            return fake_hook_handle

        @staticmethod
        def GetMessageW(_msg_ref, _hwnd, _min, _max):
            return 0  # exit pump immediately cleanly

        @staticmethod
        def TranslateMessage(_msg_ref):
            return 0

        @staticmethod
        def DispatchMessageW(_msg_ref):
            return 0

        @staticmethod
        def UnhookWindowsHookEx(handle):
            hook_calls["unhooked"] = handle == fake_hook_handle
            return 1

        @staticmethod
        def PostThreadMessageW(_tid, _msg, _w, _l):
            hook_calls["posted_quit"] = True
            return 1

        @staticmethod
        def SetCursorPos(x, y):
            hook_calls["cursor"] = (x, y)
            return 1

        @staticmethod
        def CallNextHookEx(_hhk, _code, _w, _l):
            return 0

    class _FakeKernel32:
        @staticmethod
        def GetModuleHandleW(_name):
            return 1

        @staticmethod
        def GetCurrentThreadId():
            return 777

    fake_windll = SimpleNamespace(user32=_FakeUser32, kernel32=_FakeKernel32, shcore=None)
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr(ctypes, "windll", fake_windll, raising=False)

    interceptor = SystemCursorInterceptor(lambda kind, x, y, _now: (x, y))
    ok, _err = interceptor.start()
    assert ok is True
    assert interceptor.mode == "win32_wh_mouse_ll"
    interceptor.stop()
    assert hook_calls["unhooked"] is True
    assert hook_calls["posted_quit"] is True
    assert interceptor.mode == "idle"

    # Mock Windows UI Automation neighborhood probe
    class _FakeAuto:
        @staticmethod
        def ControlFromPoint(x, y):
            if x < 100:
                return SimpleNamespace(
                    ControlTypeName="TextControl",
                    Name="Static Label",
                    BoundingRectangle=SimpleNamespace(left=10, top=10, right=80, bottom=30),
                )
            return SimpleNamespace(
                ControlTypeName="ButtonControl",
                Name="Confirm Visit",
                BoundingRectangle=SimpleNamespace(left=120, top=80, right=240, bottom=124),
            )

    monkeypatch.setitem(sys.modules, "uiautomation", _FakeAuto)
    wells = _windows_uia_probe(110.0, 100.0)
    assert len(wells) == 1
    assert wells[0].role == "ButtonControl"
    assert wells[0].title == "Confirm Visit"
