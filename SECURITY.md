# ClearCursor Security Policy

## Reporting a Vulnerability

If you discover a security vulnerability in ClearCursor, please report it privately before opening a public issue:

- Submit a report using GitHub Private Vulnerability Reporting under the repository's **Security** tab (**Report a vulnerability**).
- If possible, include reproduction steps, affected OS/version, and impact details.

## Local Architecture & Threat Model

ClearCursor runs a native desktop shell (Tauri v2) paired with a local Python FastAPI sidecar.

1. **Loopback Binding Only**
   The FastAPI and WebSocket server binds exclusively to `127.0.0.1` on an available local port. It does not listen on external network interfaces.

2. **Per-Launch Session Token**
   When launched by the Tauri desktop shell, the shell generates a random 128-bit session token and passes it to the sidecar via `CLEARCURSOR_API_TOKEN`. Every `/api/*` endpoint (except `/api/health`) requires `X-ClearCursor-Token`, and `/ws/telemetry` validates `?token=`, preventing arbitrary browser tabs from reading telemetry or toggling OS pointer hooks.

3. **Strict Content Security Policy**
   The Tauri desktop webview enforces a Content Security Policy (`default-src 'self'`) restricting network connections to `127.0.0.1` and `localhost`.

4. **OS Permission Scope**
   - **macOS Accessibility & Input Monitoring:** Required only when System-Wide Cursor Intercept or Button Magnetism (Gravity Wells) is enabled. Never captures keystroke text; only reads modifier key state (`Alt`, `Shift`, `Ctrl`, `Fn`) when checking your configured Hold-to-Bypass or Precision Slow-Mode key.
   - **Windows `WH_MOUSE_LL` Hook:** Intercepts pointer events on the active desktop session. Because of Windows User Interface Privilege Isolation (UIPI), a non-elevated ClearCursor process cannot modify pointer events over elevated Administrator windows.
   - **Camera Access:** Requested only when GazeControl is turned on by the user.

5. **CSV Formula-Injection Protection**
   All user-entered profile names, diary labels, and notes exported to CSV are sanitized against leading formula characters (`=`, `+`, `-`, `@`, tab, carriage return).
