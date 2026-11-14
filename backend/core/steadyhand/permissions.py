"""Cross-platform OS Accessibility, Input Monitoring, and Camera permission helpers."""

from __future__ import annotations

import subprocess
import sys


def get_system_permissions(*, prompt: bool = False) -> dict:
    """Inspect OS pointer/accessibility permission state across macOS, Windows, and Linux."""
    if sys.platform == "darwin":
        ax_trusted = True
        input_monitoring = True
        message: str | None = None

        try:
            import ApplicationServices as AS  # type: ignore[import-not-found]

            if prompt and hasattr(AS, "AXIsProcessTrustedWithOptions"):
                ax_trusted = bool(
                    AS.AXIsProcessTrustedWithOptions({"AXTrustedCheckOptionPrompt": True})
                )
            elif hasattr(AS, "AXIsProcessTrusted"):
                ax_trusted = bool(AS.AXIsProcessTrusted())
        except Exception as exc:
            ax_trusted = False
            message = f"Accessibility API unavailable ({exc})."

        try:
            import Quartz  # type: ignore[import-not-found]

            if prompt and hasattr(Quartz, "CGRequestListenEventAccess"):
                input_monitoring = bool(Quartz.CGRequestListenEventAccess())
            elif hasattr(Quartz, "CGPreflightListenEventAccess"):
                input_monitoring = bool(Quartz.CGPreflightListenEventAccess())
        except Exception:
            pass

        if not ax_trusted and message is None:
            message = (
                "macOS Accessibility permission is needed for system-wide cursor stabilization "
                "and button Magnetism. Click Prompt or Open Settings to grant access."
            )
        elif not input_monitoring and message is None:
            message = (
                "macOS Input Monitoring permission is recommended so the HID event tap can smooth "
                "pointer motion without cursor echo."
            )

        return {
            "platform": "macos",
            "accessibility_trusted": ax_trusted,
            "input_monitoring_trusted": input_monitoring,
            "needs_prompt": not (ax_trusted and input_monitoring),
            "message": message,
        }

    if sys.platform.startswith("win"):
        return {
            "platform": "windows",
            "accessibility_trusted": True,
            "input_monitoring_trusted": True,
            "needs_prompt": False,
            "message": (
                "Windows global WH_MOUSE_LL hook ready. Note: elevated Administrator windows "
                "(UIPI) do not receive non-elevated pointer hooks."
            ),
        }

    return {
        "platform": sys.platform,
        "accessibility_trusted": True,
        "input_monitoring_trusted": True,
        "needs_prompt": False,
        "message": None,
    }


def open_permission_settings(target: str = "accessibility") -> bool:
    """Open OS Privacy & Security settings pane for Accessibility, Input Monitoring, or Camera."""
    normalized = (target or "accessibility").strip().lower()
    if sys.platform == "darwin":
        uris = {
            "accessibility": "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility",
            "input_monitoring": "x-apple.systempreferences:com.apple.preference.security?Privacy_ListenEvent",
            "camera": "x-apple.systempreferences:com.apple.preference.security?Privacy_Camera",
        }
        uri = uris.get(normalized, uris["accessibility"])
        try:
            subprocess.Popen(["open", uri])
            return True
        except Exception:
            return False

    if sys.platform.startswith("win"):
        uris = {
            "accessibility": "ms-settings:easeofaccess-mouse",
            "input_monitoring": "ms-settings:easeofaccess-mouse",
            "camera": "ms-settings:privacy-webcam",
        }
        uri = uris.get(normalized, uris["accessibility"])
        try:
            subprocess.Popen(["cmd", "/c", "start", "", uri])
            return True
        except Exception:
            return False

    return False
