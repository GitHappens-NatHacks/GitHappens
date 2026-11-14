"""Standalone desktop sidecar entry point for TrueCursor.

Binds FastAPI + Uvicorn on localhost (default 8000 with automatic free-port fallback),
prints a single readiness line (`TRUECURSOR_READY port=<PORT>`) once bound, and cleanly
releases OpenCV camera captures and OS pointer hooks on SIGTERM/SIGINT.
"""

from __future__ import annotations

import atexit
import os
import signal
import socket
import sys
import tempfile
from pathlib import Path

if not os.environ.get("MPLCONFIGDIR"):
    mpl_dir = Path(tempfile.gettempdir()) / "truecursor_mpl"
    mpl_dir.mkdir(parents=True, exist_ok=True)
    os.environ["MPLCONFIGDIR"] = str(mpl_dir)

import uvicorn

from backend.api.main import create_app
from backend.db.database import default_user_db_path


def _bind_local_socket(host: str, preferred_port: int) -> tuple[socket.socket, int]:
    """Bind preferred port on localhost, falling back to an ephemeral free port."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        sock.bind((host, preferred_port))
    except OSError:
        sock.bind((host, 0))
    sock.listen(128)
    sock.setblocking(False)
    port = int(sock.getsockname()[1])
    return sock, port


def run_sidecar(host: str = "127.0.0.1", preferred_port: int = 8000) -> int:
    """Start Uvicorn with graceful shutdown handlers and readiness output."""
    db_path = Path(os.environ.get("TRUECURSOR_DB_PATH") or default_user_db_path())
    db_path.parent.mkdir(parents=True, exist_ok=True)
    os.environ["TRUECURSOR_DB_PATH"] = str(db_path)

    app = create_app(db_path=db_path, auto_start_workers=True)
    sock, port = _bind_local_socket(host, preferred_port)

    config = uvicorn.Config(
        app,
        host=host,
        port=port,
        log_level=os.environ.get("TRUECURSOR_LOG_LEVEL", "warning"),
        access_log=False,
    )
    server = uvicorn.Server(config)
    cleaned = False

    def _shutdown_engine() -> None:
        nonlocal cleaned
        if cleaned:
            return
        cleaned = True
        coord = getattr(app.state, "coordinator", None)
        if coord is not None:
            try:
                coord.shutdown()
            except Exception:
                pass

    def _handle_signal(_signum: int, _frame: object) -> None:
        server.should_exit = True
        _shutdown_engine()

    signal.signal(signal.SIGINT, _handle_signal)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, _handle_signal)
    atexit.register(_shutdown_engine)

    # Emit machine-readable readiness line for Tauri sidecar stdout parser.
    print(f"TRUECURSOR_READY port={port}", flush=True)
    try:
        server.run(sockets=[sock])
    finally:
        _shutdown_engine()
        try:
            sock.close()
        except OSError:
            pass
    return 0


def main() -> int:
    host = os.environ.get("TRUECURSOR_HOST", "127.0.0.1")
    try:
        preferred = int(os.environ.get("TRUECURSOR_PORT", "8000"))
    except ValueError:
        preferred = 8000
    if len(sys.argv) > 1:
        try:
            preferred = int(sys.argv[1])
        except ValueError:
            pass
    return run_sidecar(host=host, preferred_port=preferred)


if __name__ == "__main__":
    raise SystemExit(main())
