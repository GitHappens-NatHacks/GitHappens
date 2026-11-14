"""FastAPI application factory and lifespan management for TrueCursor."""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.routes import router as api_router
from backend.api.ws import ws_router
from backend.core.engine.coordinator import EngineCoordinator
from backend.db.database import DEFAULT_DB_PATH, Database


def create_app(
    coordinator: EngineCoordinator | None = None,
    db_path: str | Path = DEFAULT_DB_PATH,
    auto_start_workers: bool = True,
) -> FastAPI:
    owns_coordinator = coordinator is None

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
        title="TrueCursor API",
        version="0.1.0",
        description="Decoupled motor stabilization and gaze tracking backend.",
        lifespan=lifespan,
    )

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
