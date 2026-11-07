# SmartInterface implementation — GitHappens / natHacks 2026

## What this update implements

- The **Interface & communication** page now has functioning live text-size controls, colour themes, and letter-spacing preview.
- Changing **Text size** applies a proportional font-size adjustment to the **entire AccessShift application**, not just the preview.
- The **Colour theme** changes colours of the AccessShift main window and its pages. High contrast, warm and cool variants are included.
- An interactive, large-text **live preview** updates with text-size, letter-spacing and theme preferences.
- An **optional desktop tint** creates low-opacity, mouse-transparent Qt overlay windows on all detected displays; warm, cool and rose filters are available. It is OFF by default on every launch and disappears when the app exits.
- The settings are stored with the existing `AccessibilitySettings` / `QSettings` persistence layer. `preferences_changed` contains the new fields for integration.

## Important limits

- **This does not replace fonts in every third-party application.** macOS and Windows don't expose a universal API for replacing the text rendering of all programs.
- Desktop tint is a **transparent overlay** and doesn't change individual pixels, invert contrasts or apply a colour-management profile. It is intended as a demo/prototype and may behave differently on some window managers, multiple desktops, fullscreen windows, screen sharing or OS permission settings.
- `letter_spacing_px` currently changes the live preview and is supplied to future supported web/app adapters, but not every label within AccessShift.
- `reduce_complexity` remains an integration preference: real interface restructuring of arbitrary sites needs browser or application-specific adapters.
- **No background system service, camera access, or privileged OS APIs are activated by this UI update.**

## Developer API / Integration

No direct changes are needed to the team's gaze, speech or SteadyHand modules.

The existing main window emits `preferences_changed(dict)` whenever settings change:

```python
window.preferences_changed.connect(lambda settings: print(settings))
```

New dictionary keys:

```python
{
    "font_size_pct": 130,
    "color_profile": "high_contrast",  # standard / high_contrast / warm / cool
    "letter_spacing_px": 2,
    "tint_color": "warm",           # warm / cool / rose
    "tint_opacity": 15,             # 5..28
    "smart_interface": True,
}
```

Desktop tint on/off is intentionally NOT persisted. It is a temporary visual effect controlled by the user within the application, to avoid inadvertently overlaying screens after a restart. `window.tint_manager.active` reports current in-session state.

Extension points:

- `accessshift.modules.smartinterface.visual_controller.apply_accessshift_appearance`: in-app font/theme styling
- `accessshift.modules.smartinterface.visual_controller.VisualPreview`: live demo
- `accessshift.modules.smartinterface.screen_overlay.ScreenTintManager`: optional tint across displays
- `accessshift.ui.control_center.MainWindow._change_option`: receives control updates

For actual website font/layout modification, implement a separate browser content-script/extension receiving the visual preferences. For changing native OS text size, use supported platform accessibility APIs/settings (which vary across macOS and Windows), and don't claim arbitrary application support.

## How to launch

From your existing GitHappens repository after running this ZIP's installer:

```bash
source ~/.venvs/accessshift/bin/activate  # user's known working Mac environment
python -m accessshift
```

On Windows, activate its own venv and use `python -m accessshift`.

Open **Interface & speech**, try the **Text size**, **Colour theme**, **Letter spacing**, and **Screen tint** settings. The desktop tint feature should be manually enabled; it is safe to turn off inside the same page or by closing the application.
