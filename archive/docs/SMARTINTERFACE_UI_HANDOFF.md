# SmartInterface v0.5 — integration / UI handoff

## Scope

This release is an **application frontend** and local healthcare demonstration. SmartInterface does not alter arbitrary websites, native Windows/macOS app fonts, or desktop colours.

## Navigation (key → visible name)

| Key | Label | Live function |
|---|---|---|
| `overview` | Dashboard | Selected features, setup, status |
| `personalize` | My accessibility profile | Presets and feature toggles (persisted) |
| `gaze` | Eye & blink control | Config and calibration-request signal (backend pending) |
| `steady` | SteadyHand | Strength, target size and demo link |
| `interface` | SmartInterface | Font size, letter spacing, themes, local tint, local demo launch |
| `speech` | Communication | Speech module settings and test message, TTS backend dependent |
| `test` | Demo Lab & tests | Two-window healthcare demo launcher, in-app tremor test |

## Important signals and services

- `MainWindow.preferences_changed(dict)` fires when a saved setting changes; `MainWindow._update_live_demo()` passes these to the local healthcare dialog.
- `MainWindow.calibration_requested` is the eye-tracking module hook.
- `MainWindow.assistance_changed` is a reserved signal, not an operational OS-level controller.
- `MainWindow.tint_manager.register_window(widget)` registers **only this app's** windows for local tint. No screen enumeration occurs.
- `MainWindow.tint_manager.update(color='warm'|'cool'|'rose', opacity=0..20)` adjusts the window-local translucent overlay; `enable()` and `disable()` control its visibility. OFF is the startup state.
- `QSettings('GitHappens','AccessShift AI')` saves the prior preference schema unchanged except that tint intensity is now capped at 20%.
- `HealthcareDemoWindow.apply_preferences(dict)` updates the **same** form components with no reload or data copy. `demo_submitted`, `mode_changed`, `target_activated` remain for integration.

## Working vs pending

**Working UI:** profile settings, saved visual preferences, local tint in app+demo windows, independent second-window demo, form adaptation with shared data, in-app SteadyHand test.

**Pending external integrations:** OS-level pointer control, camera worker and calibration, AI-generated simplification, predictive text, third-party website adaptation. Speech preview depends on the team-installed backend.

## Team boundaries

Frontend edits: `accessshift/ui/*` and `accessshift/modules/smartinterface/{visual_controller,screen_overlay}.py`.
Other teammates' modules under `modules/gaze`, `modules/steadyhand`, `modules/speech`, and `engine` are not changed by this installer.
