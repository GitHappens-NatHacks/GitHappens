"""REST API endpoints for TrueCursor settings, calibration, engine toggles, and history."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request

from backend.api.schemas import (
    CalibrateRequest,
    CalibrateResponse,
    EngineToggleRequest,
    EngineToggleResponse,
    PermissionPromptRequest,
    PointerSampleRequest,
    SettingsPayload,
    SettingsUpdateRequest,
)
from backend.core.engine.coordinator import EngineCoordinator
from backend.core.steadyhand.displays import detect_displays, virtual_screen_rect
from backend.core.steadyhand.permissions import (
    get_system_permissions,
    open_permission_settings,
)

router = APIRouter(prefix="/api", tags=["truecursor"])


def _coordinator(request: Request) -> EngineCoordinator:
    return request.app.state.coordinator


@router.get("/health")
def health(request: Request) -> dict:
    coord = _coordinator(request)
    snap = coord.telemetry_snapshot()
    return {
        "status": "ok",
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


@router.get("/history")
def get_history(
    request: Request,
    limit: int = Query(200, ge=1, le=1000),
    session_only: bool = False,
) -> dict:
    coord = _coordinator(request)
    session_id = coord.session_id if session_only else None
    return {
        "session_id": coord.session_id,
        "tremor_history": coord.db.get_tremor_history(limit=limit, session_id=session_id),
        "calibration_profiles": coord.db.list_calibration_profiles(limit=20),
    }


@router.get("/sessions")
def get_sessions(
    request: Request,
    days: int = Query(14, ge=1, le=365),
    limit: int = Query(30, ge=1, le=500),
) -> dict:
    coord = _coordinator(request)
    summary = coord.db.get_session_summaries(days=days, limit=limit)
    return {
        "active_session_id": coord.session_id,
        **summary,
        "calibration_profiles": coord.db.list_calibration_profiles(limit=10),
    }


@router.post("/steadyhand/sample")
def push_steadyhand_sample(payload: PointerSampleRequest, request: Request) -> dict:
    coord = _coordinator(request)
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
