"""Tests for standalone sidecar configuration, port fallback, and packaged DB paths."""

from __future__ import annotations

import socket
from pathlib import Path

from backend import sidecar_main
from backend.api.main import create_app
from backend.db.database import default_user_db_path


def test_default_user_db_path_honors_env_and_frozen(monkeypatch, tmp_path: Path):
    explicit = tmp_path / "custom.db"
    monkeypatch.setenv("CLEARCURSOR_DB_PATH", str(explicit))
    assert default_user_db_path() == explicit

    monkeypatch.delenv("CLEARCURSOR_DB_PATH", raising=False)
    legacy = tmp_path / "legacy.db"
    monkeypatch.setenv("TRUECURSOR_DB_PATH", str(legacy))
    assert default_user_db_path() == legacy

    monkeypatch.delenv("TRUECURSOR_DB_PATH", raising=False)
    monkeypatch.setattr(sidecar_main.sys, "frozen", True, raising=False)
    frozen_path = default_user_db_path()
    assert frozen_path.name == "clearcursor.db"
    assert "ClearCursor" in str(frozen_path)


def test_sidecar_bind_local_socket_falls_back_when_port_occupied():
    blocker = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    blocker.bind(("127.0.0.1", 0))
    blocker.listen(1)
    occupied_port = blocker.getsockname()[1]

    sock, bound_port = sidecar_main._bind_local_socket("127.0.0.1", occupied_port)
    try:
        assert bound_port != occupied_port
        assert bound_port > 0
    finally:
        sock.close()
        blocker.close()


def test_create_app_allows_tauri_cors_origins(tmp_path: Path):
    app = create_app(db_path=tmp_path / "cors.db", auto_start_workers=False)
    cors_middleware = next(m for m in app.user_middleware if m.cls.__name__ == "CORSMiddleware")
    origins = cors_middleware.kwargs["allow_origins"]
    assert "tauri://localhost" in origins
    assert "http://tauri.localhost" in origins
