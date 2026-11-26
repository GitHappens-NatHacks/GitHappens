"""REST API endpoints for ClearCursor settings, calibration, engine toggles, events, and history."""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from backend.api.schemas import (
    CalibrateRequest,
    CalibrateResponse,
    ClinicalEventRequest,
    EngineToggleRequest,
    EngineToggleResponse,
    MotorCheckinRequest,
    PermissionPromptRequest,
    PointerSampleRequest,
    SettingsPayload,
    SettingsUpdateRequest,
)
from backend.core.engine.coordinator import EngineCoordinator
from backend.core.licensing import get_edition_capabilities
from backend.core.steadyhand.displays import detect_displays, virtual_screen_rect
from backend.core.steadyhand.permissions import (
    get_system_permissions,
    open_permission_settings,
)

router = APIRouter(prefix="/api", tags=["clearcursor"])


def _coordinator(request: Request) -> EngineCoordinator:
    return request.app.state.coordinator


@router.get("/health")
def health(request: Request) -> dict:
    coord = _coordinator(request)
    snap = coord.telemetry_snapshot()
    caps = get_edition_capabilities()
    return {
        "status": "ok",
        "app": "ClearCursor",
        "edition": caps.edition,
        "session_id": coord.session_id,
        "steadyhand_running": coord.steady_worker.running,
        "gaze_running": coord.gaze_controller.running,
        "calibrated": snap["gaze"]["calibrated"],
    }


@router.get("/settings", response_model=SettingsPayload)
def get_settings(request: Request) -> SettingsPayload:
    coord = _coordinator(request)
    return SettingsPayload(**coord.settings.as_dict())


@router.post("/settings", response_model=SettingsPayload)
def update_settings(payload: SettingsUpdateRequest, request: Request) -> SettingsPayload:
    coord = _coordinator(request)
    updated = coord.update_settings(payload.model_dump(exclude_none=True))
    return SettingsPayload(**updated.as_dict())


@router.post("/calibrate", response_model=CalibrateResponse)
def calibrate(payload: CalibrateRequest, request: Request) -> CalibrateResponse:
    coord = _coordinator(request)
    try:
        if payload.mode == "head":
            if not payload.poses:
                raise ValueError("poses dict is required when mode='head'")
            result = coord.calibrate_head_poses(
                poses=payload.poses,
                open_ears=payload.open_ears,
                profile_name=payload.profile_name,
            )
        else:
            if not payload.features or not payload.targets:
                raise ValueError("features and targets are required when mode='dots'")
            result = coord.calibrate_dots(
                source=payload.source,
                features=payload.features,
                targets=payload.targets,
                open_ears=payload.open_ears,
                profile_name=payload.profile_name,
            )
        return CalibrateResponse(**result)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/engine/toggle", response_model=EngineToggleResponse)
def toggle_engine(payload: EngineToggleRequest, request: Request) -> EngineToggleResponse:
    coord = _coordinator(request)
    result = coord.toggle(
        assistance_enabled=payload.assistance_enabled,
        steady_hand=payload.steady_hand,
        gaze_control=payload.gaze_control,
        simulate_tremor=payload.simulate_tremor,
        system_mouse=payload.system_mouse,
        camera=payload.camera,
        camera_index=payload.camera_index,
    )
    return EngineToggleResponse(
        settings=SettingsPayload(**result["settings"]),
        camera_running=result["camera_running"],
        steadyhand_running=result["steadyhand_running"],
    )


@router.post("/engine/emergency-stop", response_model=EngineToggleResponse)
def emergency_stop_all(request: Request) -> EngineToggleResponse:
    """Stop GazeControl and release OS pointer interception immediately."""
    coord = _coordinator(request)
    result = coord.emergency_stop_all()
    return EngineToggleResponse(
        settings=SettingsPayload(**result["settings"]),
        camera_running=result["camera_running"],
        steadyhand_running=result["steadyhand_running"],
    )


class GazePauseRequest(BaseModel):
    paused: bool


@router.post("/gaze/pause")
def pause_gaze(payload: GazePauseRequest, request: Request) -> dict:
    """Pause or resume GazeControl pointer/dwell output while keeping camera live."""
    coord = _coordinator(request)
    return coord.pause_gaze(payload.paused)


@router.post("/gaze/stop", response_model=EngineToggleResponse)
def stop_gaze_emergency(request: Request) -> EngineToggleResponse:
    """Emergency stop for GazeControl, webcam capture, and gaze cursor output."""
    coord = _coordinator(request)
    result = coord.emergency_stop_gaze()
    return EngineToggleResponse(
        settings=SettingsPayload(**result["settings"]),
        camera_running=result["camera_running"],
        steadyhand_running=result["steadyhand_running"],
    )


@router.post("/gaze/clear-calibration")
def clear_gaze_calibration(request: Request) -> dict:
    """Clear active gaze calibration so the cursor stops until recalibrated."""
    coord = _coordinator(request)
    return coord.clear_calibration()


@router.get("/gaze/preview")
async def gaze_preview(request: Request) -> StreamingResponse:
    """Stream live mirrored webcam frames as MJPEG while GazeControl is running."""
    coord = _coordinator(request)

    async def frame_stream():
        last_seq = -1
        for _ in range(40):
            if coord.gaze_controller.running:
                break
            if await request.is_disconnected():
                return
            await asyncio.sleep(0.05)

        while coord.gaze_controller.running:
            if await request.is_disconnected():
                break
            seq = coord.gaze_controller._frame_seq
            if seq != last_seq:
                jpeg = coord.gaze_controller.latest_preview_jpeg()
                if jpeg is not None:
                    last_seq = seq
                    yield (
                        b"--frame\r\n"
                        b"Content-Type: image/jpeg\r\n\r\n" + jpeg + b"\r\n"
                    )
            await asyncio.sleep(0.025)

    return StreamingResponse(
        frame_stream(),
        media_type="multipart/x-mixed-replace; boundary=frame",
        headers={"Cache-Control": "no-store, no-cache, must-revalidate"},
    )


@router.get("/history")
def get_history(
    request: Request,
    limit: int = Query(200, ge=1, le=1000),
    session_only: bool = False,
    include_simulated: bool = True,
) -> dict:
    coord = _coordinator(request)
    session_id = coord.session_id if session_only else None
    return {
        "session_id": coord.session_id,
        "tremor_history": coord.db.get_tremor_history(
            limit=limit, session_id=session_id, include_simulated=include_simulated
        ),
        "calibration_profiles": coord.db.list_calibration_profiles(limit=20),
    }


@router.get("/sessions")
def get_sessions(
    request: Request,
    days: int = Query(14, ge=1, le=365),
    limit: int = Query(30, ge=1, le=500),
    include_simulated: bool = False,
) -> dict:
    coord = _coordinator(request)
    summary = coord.db.get_session_summaries(
        days=days, limit=limit, include_simulated=include_simulated
    )
    cadence = coord.db.get_keyboard_cadence(days=days, limit=100)
    return {
        "active_session_id": coord.session_id,
        **summary,
        "clinical_events": coord.db.list_clinical_events(days=days, limit=200),
        "motor_checkins": coord.db.list_motor_checkins(days=days, limit=100),
        "keyboard_cadence_summary": cadence["summary"],
        "keyboard_cadence_windows": cadence["windows"],
        "calibration_profiles": coord.db.list_calibration_profiles(limit=10),
    }


@router.get("/checkins")
def list_checkins(
    request: Request,
    days: int = Query(30, ge=1, le=365),
    limit: int = Query(100, ge=1, le=500),
) -> dict:
    coord = _coordinator(request)
    checkins = coord.db.list_motor_checkins(days=days, limit=limit)
    return {"checkins": checkins}


@router.post("/checkins")
def create_checkin(payload: MotorCheckinRequest, request: Request) -> dict:
    coord = _coordinator(request)
    try:
        return coord.record_motor_checkin(
            hold_samples=[pt.model_dump() for pt in payload.hold_samples],
            target_x=payload.target_x,
            target_y=payload.target_y,
            taps=[tp.model_dump() for tp in payload.taps],
            tap_hit_radius_px=payload.tap_hit_radius_px,
            context_tag=payload.context_tag,
            notes=payload.notes,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/checkins/{checkin_id}")
def delete_checkin(checkin_id: int, request: Request) -> dict:
    coord = _coordinator(request)
    deleted = coord.db.delete_motor_checkin(checkin_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Motor check-in not found.")
    return {"deleted": True, "id": checkin_id}


@router.get("/cadence")
def get_keyboard_cadence(
    request: Request,
    days: int = Query(30, ge=1, le=365),
    limit: int = Query(100, ge=1, le=500),
) -> dict:
    coord = _coordinator(request)
    return {
        "enabled": coord.settings.keyboard_cadence_telemetry,
        **coord.db.get_keyboard_cadence(days=days, limit=limit),
    }


@router.get("/events")
def list_events(
    request: Request,
    days: int = Query(30, ge=1, le=365),
    limit: int = Query(200, ge=1, le=500),
) -> dict:
    coord = _coordinator(request)
    return {
        "events": coord.db.list_clinical_events(days=days, limit=limit),
    }


@router.post("/events")
def create_event(payload: ClinicalEventRequest, request: Request) -> dict:
    coord = _coordinator(request)
    return coord.db.add_clinical_event(
        event_type=payload.event_type,
        label=payload.label,
        timestamp=payload.timestamp,
        dosage=payload.dosage,
        severity=payload.severity,
        notes=payload.notes,
    )


@router.delete("/events/{event_id}")
def delete_event(event_id: int, request: Request) -> dict:
    coord = _coordinator(request)
    deleted = coord.db.delete_clinical_event(event_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Clinical event not found.")
    return {"deleted": True, "id": event_id}


@router.post("/steadyhand/sample")
def push_steadyhand_sample(payload: PointerSampleRequest, request: Request) -> dict:
    coord = _coordinator(request)
    if payload.sandbox:
        return coord.sandbox_worker.process_sample(
            payload.x,
            payload.y,
            timestamp=payload.timestamp,
            pressed=payload.pressed,
        )
    snap = coord.steady_worker.process_sample(
        payload.x,
        payload.y,
        timestamp=payload.timestamp,
        pressed=payload.pressed,
    )
    coord.persist_pending_fft()
    return snap


@router.get("/system/permissions")
def system_permissions() -> dict:
    return get_system_permissions(prompt=False)


@router.post("/system/permissions/prompt")
def prompt_system_permissions(payload: PermissionPromptRequest) -> dict:
    perms = get_system_permissions(prompt=True)
    opened = open_permission_settings(payload.target) if payload.open_settings else False
    return {
        **perms,
        "settings_opened": opened,
    }


@router.get("/system/displays")
def system_displays(request: Request) -> dict:
    coord = _coordinator(request)
    displays = detect_displays(coord.settings.screen_width, coord.settings.screen_height)
    coord._cached_displays = displays
    vrect = virtual_screen_rect(
        displays,
        fallback_width=coord.settings.screen_width,
        fallback_height=coord.settings.screen_height,
    )
    return {
        "virtual_rect": {
            "left": vrect.left,
            "top": vrect.top,
            "width": vrect.width,
            "height": vrect.height,
        },
        "displays": [d.as_dict() for d in displays],
    }
