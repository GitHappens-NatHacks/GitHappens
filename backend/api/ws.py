"""WebSocket endpoint streaming real-time telemetry at 20-30 Hz."""

from __future__ import annotations

import asyncio
import hmac

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

ws_router = APIRouter(tags=["telemetry"])

DEFAULT_STREAM_HZ = 30.0
MIN_STREAM_HZ = 20.0
MAX_STREAM_HZ = 30.0
DISCONNECT_STOP_GRACE_S = 2.0


async def _stop_gaze_when_abandoned(app, coord) -> None:
    """Stop camera GazeControl when UI disconnects, preserving tray SteadyHand smoothing."""
    try:
        await asyncio.sleep(DISCONNECT_STOP_GRACE_S)
        if getattr(app.state, "active_ws_clients", 0) <= 0:
            if coord.gaze_controller.running or coord.settings.gaze_control:
                coord.stop_gaze_on_disconnect()
    except asyncio.CancelledError:
        return


def _ws_token_authorized(websocket: WebSocket) -> bool:
    expected = getattr(websocket.app.state, "api_token", None)
    if not expected:
        return True
    provided = (
        websocket.query_params.get("token")
        or websocket.headers.get("x-clearcursor-token")
        or ""
    )
    return hmac.compare_digest(str(provided), str(expected))


@ws_router.websocket("/ws/telemetry")
async def telemetry_stream(websocket: WebSocket, hz: float = DEFAULT_STREAM_HZ) -> None:
    if not _ws_token_authorized(websocket):
        await websocket.close(code=1008)
        return

    await websocket.accept()
    clamped_hz = max(MIN_STREAM_HZ, min(MAX_STREAM_HZ, float(hz)))
    interval = 1.0 / clamped_hz
    state = websocket.app.state
    coord = state.coordinator

    pending = getattr(state, "ws_cleanup_task", None)
    if pending is not None and not pending.done():
        pending.cancel()
    state.active_ws_clients = int(getattr(state, "active_ws_clients", 0)) + 1

    try:
        while True:
            payload = coord.telemetry_snapshot()
            await websocket.send_json(payload)
            await asyncio.sleep(interval)
    except WebSocketDisconnect:
        return
    except Exception:
        return
    finally:
        state.active_ws_clients = max(0, int(getattr(state, "active_ws_clients", 1)) - 1)
        if state.active_ws_clients == 0:
            state.ws_cleanup_task = asyncio.create_task(_stop_gaze_when_abandoned(websocket.app, coord))
