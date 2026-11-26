"""FastAPI application factory, local auth middleware, and lifespan management for ClearCursor."""

from __future__ import annotations

import hmac
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.api.routes import router as api_router
from backend.api.ws import ws_router
from backend.core.engine.coordinator import EngineCoordinator
from backend.db.database import DEFAULT_DB_PATH, Database


def create_app(
    coordinator: EngineCoordinator | None = None,
    db_path: str | Path = DEFAULT_DB_PATH,
    auto_start_workers: bool = True,
    api_token: str | None = None,
) -> FastAPI:
    owns_coordinator = coordinator is None
    resolved_token = (
        api_token
        if api_token is not None
        else os.environ.get("CLEARCURSOR_API_TOKEN", "").strip() or None
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if coordinator is None:
            db = Database(db_path)
            app.state.coordinator = EngineCoordinator(
                db=db,
                auto_start_workers=auto_start_workers,
            )
        else:
            app.state.coordinator = coordinator
        try:
            yield
        finally:
            if owns_coordinator:
                app.state.coordinator.shutdown()

    app = FastAPI(
        title="ClearCursor API",
        version="0.2.0",
        description="Decoupled motor stabilization, gaze tracking, and clinician telemetry backend.",
        lifespan=lifespan,
    )
    app.state.api_token = resolved_token

    if resolved_token:
        @app.middleware("http")
        async def verify_local_api_token(request: Request, call_next):
            if request.method == "OPTIONS" or request.url.path == "/api/health":
                return await call_next(request)
            if request.url.path.startswith("/api/"):
                header_token = request.headers.get("X-ClearCursor-Token", "")
                if not header_token:
                    auth = request.headers.get("Authorization", "")
                    if auth.lower().startswith("bearer "):
                        header_token = auth[7:].strip()
                if not header_token:
                    header_token = request.query_params.get("token", "")
                if not hmac.compare_digest(header_token, resolved_token):
                    return JSONResponse(
                        status_code=401,
                        content={"detail": "Missing or invalid ClearCursor local session token."},
                    )
            return await call_next(request)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "tauri://localhost",
            "http://tauri.localhost",
            "https://tauri.localhost",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(api_router)
    app.include_router(ws_router)
    return app


app = create_app()
