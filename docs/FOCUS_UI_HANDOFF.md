# AccessShift Focus UI 2.0 — integration handoff

## Scope

Replaces the old multi-page sidebar dashboard with a top-navigation interface:
**Assist**, **Settings**, **Demo**. The local healthcare demo still opens as a
second window through `accessshift.ui.main_window.MainWindow`.

This is **not** a browser extension or system-wide font changer. Feature switches
represent saved user preferences, not proof that a camera/OS service is running.

## Public interfaces retained

- `MainWindow(repo_root)` in `accessshift.ui.main_window`
- `preferences_changed(dict)` Qt signal
- `calibration_requested()` Qt signal
- `assistance_changed(bool)` signal kept for future service manager
- `window.engine`, `window.steady`, `window.prefs`, `window.tint_manager`
- `set_demo_launcher(callback)` and `_navigate('adjust','appearance')`
- `reset_demo_button`, `launch_demo_button` for the existing two-window wrapper
- `window.prefs.as_dict()` persisted with existing `QSettings` key

## Settings fields unchanged

`smart_interface`, `steady_hand`, `gaze_control`, `predictive_speech`,
`font_size_pct`, `color_profile`, `letter_spacing_px`, `reduce_complexity`,
`tint_enabled`, `tint_color`, `tint_opacity`, `tremor_strength`, `target_size_pct`,
`gaze_dwell_ms`, `blink_select`, `speech_rate`.

## What teammates connect

Adnan/Pragati: gaze worker => named targets in the separate local demo; do not
replace the UI with the old embedded booking window.

Yee/Dipta: SteadyHand worker and measurements. The test page currently uses
an in-app simulation; it does not alter the desktop pointer.

Avneet: speech service and predictive text. The UI includes an isolated,
non-blocking speech test, not a replacement for Avneet's speech engine.

## Validation

1. Switch to a feature branch based on recent `main`.
2. `python3 ~/Downloads/accessshift_focus_redesign/install.py`
3. `source ~/.venvs/accessshift/bin/activate`
4. `python -m accessshift`
5. Confirm window title says `AccessShift AI — Focus UI 2.0`.
6. Confirm the only top navigation is `Assist | Settings | Demo`.
7. Run `python scripts/verify_focus_ui.py` to save six real Qt screenshots.
8. Open the demo, change Display settings and confirm the second window updates
   without losing entered fictitious form data.

Do not commit `.venv`, `__pycache__`, or generated screenshots.
