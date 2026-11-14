"""Cross-platform PyInstaller bundler for the TrueCursor FastAPI sidecar.

Produces a standalone single-file executable named:
    src-tauri/binaries/truecursor-backend-<rust-target-triple>[.exe]

Usage:
    python scripts/build_backend.py
    python scripts/build_backend.py --target aarch64-apple-darwin
"""

from __future__ import annotations

import argparse
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BINARIES_DIR = ROOT / "src-tauri" / "binaries"


def detect_target_triple() -> str:
    """Resolve the Rust/Tauri target triple for the active host OS and CPU."""
    env_triple = os.environ.get("TAURI_ENV_TARGET_TRIPLE", "").strip()
    if env_triple:
        return env_triple

    machine = platform.machine().lower()
    if sys.platform == "darwin":
        arch = "aarch64" if machine in {"arm64", "aarch64"} else "x86_64"
        return f"{arch}-apple-darwin"
    if sys.platform.startswith("win"):
        arch = "aarch64" if machine in {"arm64", "aarch64"} else "x86_64"
        return f"{arch}-pc-windows-msvc"
    arch = "aarch64" if machine in {"arm64", "aarch64"} else "x86_64"
    return f"{arch}-unknown-linux-gnu"


def build_sidecar(target_triple: str) -> Path:
    """Compile backend/sidecar_main.py via PyInstaller and copy to Tauri binaries."""
    ext = ".exe" if "windows" in target_triple else ""
    output_name = f"truecursor-backend-{target_triple}"
    dist_dir = ROOT / "build" / "sidecar-dist"
    work_dir = ROOT / "build" / "sidecar-work"
    spec_dir = ROOT / "build" / "sidecar-spec"

    dist_dir.mkdir(parents=True, exist_ok=True)
    work_dir.mkdir(parents=True, exist_ok=True)
    spec_dir.mkdir(parents=True, exist_ok=True)
    BINARIES_DIR.mkdir(parents=True, exist_ok=True)

    command = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--onefile",
        "--clean",
        "--name",
        output_name,
        "--paths",
        str(ROOT),
        "--distpath",
        str(dist_dir),
        "--workpath",
        str(work_dir),
        "--specpath",
        str(spec_dir),
        "--collect-data",
        "mediapipe",
        "--collect-submodules",
        "uvicorn",
        "--collect-submodules",
        "pynput",
        "--hidden-import",
        "cv2",
        "--hidden-import",
        "fastapi",
        "--hidden-import",
        "pydantic",
        "--hidden-import",
        "sqlite3",
        "--hidden-import",
        "websockets",
    ]

    if sys.platform.startswith("win"):
        # Suppress console window in end-user Windows builds while keeping pipes active.
        command.append("--noconsole")

    models_dir = ROOT / "assets" / "models"
    if models_dir.exists() and any(p.name != ".gitkeep" for p in models_dir.iterdir()):
        command.extend(["--add-data", f"{models_dir}{os.pathsep}assets/models"])

    command.append(str(ROOT / "backend" / "sidecar_main.py"))

    print(f"[build_backend] Building {output_name}{ext} via PyInstaller...")
    subprocess.run(command, cwd=ROOT, check=True)

    built_bin = dist_dir / f"{output_name}{ext}"
    if not built_bin.exists():
        raise FileNotFoundError(f"Expected PyInstaller binary at {built_bin}")

    dest_bin = BINARIES_DIR / f"{output_name}{ext}"
    shutil.copy2(built_bin, dest_bin)
    if not sys.platform.startswith("win"):
        dest_bin.chmod(0o755)
    print(f"[build_backend] Sidecar ready at {dest_bin}")
    return dest_bin


def main() -> int:
    parser = argparse.ArgumentParser(description="Build TrueCursor Python sidecar binary.")
    parser.add_argument(
        "--target",
        default=None,
        help="Optional Rust target triple override (e.g. aarch64-apple-darwin).",
    )
    args = parser.parse_args()
    triple = args.target or detect_target_triple()
    build_sidecar(triple)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
