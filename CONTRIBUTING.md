# Contributing to ClearCursor

Thank you for helping improve ClearCursor.

## Repository Layout

- `backend/` - FastAPI REST/WebSocket server, SQLite repository, SteadyHand DSP engine, and MediaPipe GazeControl workers.
- `frontend/` - React 19, TypeScript, and Tailwind CSS desktop interface.
- `src-tauri/` - Tauri v2 Rust desktop shell, system tray menu, global shortcuts, and sidecar lifecycle.
- `chrome-extension/` - Manifest V3 browser extension sharing the One-Euro and Click-Freeze math.
- `scripts/` - Sidecar PyInstaller bundling and development utilities.
- `tests/` - Pytest suite covering DSP math, OS hooks, database migrations, API auth, and worker lifecycles.
- `archive/` - Reference snapshot of the original PySide6 hackathon prototype (`archive/legacy_ui/`).

## Local Setup

1. Create a Python 3.12 virtual environment and install dependencies:
   ```bash
   python3.12 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt -r requirements-dev.txt
   ```
2. Install frontend dependencies:
   ```bash
   npm --prefix frontend install
   ```
3. Run the development server (FastAPI sidecar + Vite UI):
   ```bash
   make dev
   ```

## Engineering Guidelines

- Keep `backend/` free of Qt imports (`tests/backend/test_architecture.py` enforces this).
- Never run blocking cross-process Accessibility or UI Automation IPC inside low-level OS mouse hook callbacks (`CGEventTap` or `WH_MOUSE_LL`). Probe asynchronously on background threads and read cached target rects inside the hook.
- Keep simulated tremor data (`simulated=1`) isolated from real-world clinician reports by default.
- Write tests for every bug fix or new feature before opening a pull request.

## Running Checks

```bash
make test
cargo check --manifest-path src-tauri/Cargo.toml
```

## Pull Request Process

1. Create a focused feature or bugfix branch from `main`.
2. Ensure Python tests, frontend Vitest/TypeScript/Vite build, Chrome extension tests, and Rust `cargo check` all pass.
3. Describe the problem, the change, and how you tested it on macOS or Windows.
