# AccessShift AI — Accessibility Control Center

This replaces the **startup UI** from `accessshift/ui/main_window.py` with an accessibility configuration application. It is **not** a healthcare booking app. The old booking portal code remains unused for a potential hackathon demonstration; it is not opened at startup.

## What ships in this frontend

- First-run personalization flow with four preset interaction configurations.
- Overview dashboard (selected modules and configuration status).
- Gaze settings: enable, blink select, dwell time, calibration integration signal.
- Mouse settings: SteadyHand enable, smoothing strength, target size.
- SmartInterface settings: enable, simplified layout and text size preferences.
- Speech controls: enable, rate, test sentence through the team's `SpeechEngine`.
- In-app tremor playground: simulated movement, raw vs smoothed cursor markers, target click accuracy.
- Local, cross-platform persistent preferences using Qt `QSettings`.
- Clear status notes that experimental integrations are not system-wide yet.

## Ownership

- `main_window.py` — intentionally **replaced** with an import shim to launch new control center. Existing `app.py` unchanged.
- `control_center.py` — all application pages, signals and event wiring.
- `control_center_components.py` — reusable controls, including accessible toggle.
- `control_center_settings.py` — data model, profiles, local settings persistence.
- `control_center_styles.qss` — shared UI tokens and Qt styling.

## API compatibility with team code

`from accessshift.ui.main_window import MainWindow`

`MainWindow(repo_root: pathlib.Path)` remains the entry point used by `accessshift/app.py`.

The window exposes:

```python
window.engine                    # existing AdaptiveEngine
window.steady                    # existing SteadyHandController
window.preferences_changed      # Qt Signal(dict) with all settings
window.calibration_requested    # Qt Signal() for Adnan's camera worker
window.assistance_changed       # reserved signal for future session manager
```

The four selected module flags match those already used by `AdaptiveEngine`:

- `gaze_control`
- `smart_interface`
- `steady_hand`
- `predictive_speech`

Integration example after window construction:

```python
def apply_preference_config(config: dict):
    print('Selected settings:', config)
    # Tell your background services to update; don't block the GUI thread.

window.preferences_changed.connect(apply_preference_config)
window.calibration_requested.connect(open_gaze_calibration)
```

Attach camera processing and OS-control workers through Qt signals/slots, **not** by updating widgets directly from worker threads. The GUI never sends camera data or medical information to the cloud. Text-to-speech is provided by the team module; predictive text is not yet implemented here.

## Not yet implemented / do not claim in the demo

1. Enabling a configuration does not itself make gaze control work across the OS. Adnan must connect the gaze worker and calibration UI.
2. `SteadyHandController.try_enable_system_mouse()` only initializes a `pynput` controller; it does not install global event interception/smoothing. The included playground is a real **in-app** test, not OS-wide correction.
3. Qt alone cannot rewrite arbitrary healthcare or third-party websites. SmartInterface needs a browser adapter/extension or selected integration. These controls store preferences for it.
4. Speech can be tested with `pyttsx3`, but ONNX predictive typing remains a team integration.
5. Settings are local. They persist across restarts using Qt's native `QSettings`, which works on macOS and Windows.

## Getting it onto your current GitHub branch

1. Open **GitHub Desktop**, confirm Current Branch is `feature/healthcare-portal-ui`.
2. Unzip `accessshift_accessibility_app.zip` in Downloads.
3. Open VS Code in your existing `GitHappens` folder, then **Terminal → New Terminal**.
4. From the `GitHappens` folder, run:

   ```bash
   python3 ~/Downloads/accessshift_accessibility_app/install.py
   ```

   If the ZIP extracts to a slightly different name/location, adjust the path to `install.py` accordingly. The installer verifies the repository and branch before changing any files. Existing target files are backed up under `.git/accessshift-ui-backups`.
5. Run:

   ```bash
   source .venv/bin/activate
   python -m accessshift
   ```

6. Optional smoke test:

   ```bash
   python scripts/smoke_test_accessshift_ui.py
   ```

7. In GitHub Desktop, inspect **Changes**, create a commit such as `Redesign AccessShift as accessibility control center`, then click **Push origin**. Open a pull request when the team is ready; publishing a branch does not merge it into main.

### Windows install

The **same files** work with Windows + PySide6. In PowerShell, activate the virtual environment with `.venv\\Scripts\\Activate.ps1` (if policy allows) or run `.venv\\Scripts\\python.exe -m accessshift`. Use `python install.py` from the extracted package while the current directory is your GitHappens repo. PyInstaller binaries must be built on each target OS. The included `scripts/build_accessshift.py` packages the new `.qss` stylesheet, which the existing basic build command would otherwise omit. Run `python scripts/build_accessshift.py` in the relevant OS environment; packaging native video/speech dependencies may need further platform testing.

## Visual structure

```text
AccessShift AI
├── Overview (readable selection summary and integration status)
├── My preferences (first-run presets and 4 accessibility tools)
├── Eye & blink control (camera settings and calibration hook)
├── Mouse stability (adaptive smoothing preferences)
├── Interface & speech (simplification, text, TTS)
└── Test & preview (working in-app tremor demo)
```

### Where to change the design

- **Colours, borders, button appearance:** `control_center_styles.qss`
- **Words, cards, page layout, navigation:** `control_center.py`
- **Switch appearance and common reusable widgets:** `control_center_components.py`
- **Profile defaults, settings fields:** `control_center_settings.py`

Do not modify `adaptive_engine.py`, `profiles.py`, `modules/gaze/*`, `modules/steadyhand/*`, or other teammates' files for this frontend change.
