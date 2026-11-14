"""WebSocket endpoint streaming real-time telemetry at 20-30 Hz."""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

ws_router = APIRouter(tags=["telemetry"])

DEFAULT_STREAM_HZ = 25.0
MIN_STREAM_HZ = 20.0
MAX_STREAM_HZ = 30.0


@ws_router.websocket("/ws/telemetry")
async def telemetry_stream(websocket: WebSocket, hz: float = DEFAULT_STREAM_HZ) -> None:
    await websocket.accept()
    clamped_hz = max(MIN_STREAM_HZ, min(MAX_STREAM_HZ, float(hz)))
    interval = 1.0 / clamped_hz
    coord = websocket.app.state.coordinator

    try:
        while True:
            payload = coord.telemetry_snapshot()
            await websocket.send_json(payload)
            await asyncio.sleep(interval)
    except WebSocketDisconnect:
        return
    except Exception:
        return
