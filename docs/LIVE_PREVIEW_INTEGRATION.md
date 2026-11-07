# AccessShift — SmartInterface live two-window demo

## Architecture

- `accessshift/ui/main_window.py` is the control center wrapper. It has the sidebar and all preferences. When **Open live healthcare demo** is clicked, it switches the main window to **Interface & speech** and opens a **separate nonmodal** `HealthcareDemoWindow`.
- `accessshift/ui/control_center.py` (already present) persists preferences and emits `preferences_changed(dict)` whenever a slider, toggle, or theme dropdown changes.
- `main_window.py` listens to that event and passes the dictionary to `HealthcareDemoWindow.apply_preferences` **only while the demo window is open**.
- `accessshift/ui/healthcare_demo_window.py` uses the same instantiated form widgets throughout: changing views does not delete or recreate input fields, and does not change actual appointment data.

## Judges' demo sequence

1. Open AccessShift, select **Test & preview → Open live healthcare demo**.
2. **Two windows** appear: (A) AccessShift, automatically on **Interface & speech**, and (B) healthcare demo, showing the *original complicated form*.
3. In B, enter a fictional first name and choose a time.
4. In A, adjust **text size**. The demo updates immediately using the current saved accessibility preferences. *Note*: if SmartInterface is enabled in saved preferences, the first change also activates the accessible layout.
5. In A, choose **High contrast** or **Warm reading**. The colours update live in B.
6. In A, adjust **letter spacing** and **target size** (the latter is under **Mouse stability**). The same B widgets update.
7. In A, toggle **Reduce complexity**. B switches between step-by-step / reduced-clutter mode and the fuller view without losing the fictional patient details.
8. In A, toggle **SmartInterface** off/on. B returns to original / adapted form.

### Why the demo starts in original mode

The initial B window is a controlled *before* baseline even if the user's saved SmartInterface setting is already on. The first preference edit causes B to adopt **all the current preferences**; after that, subsequent changes are fully synchronized. The status strip in B explains this.

### Scope and limitations

- This is an **in-process PySide6 signal connection**, not browser CSS or a local web server. It is portable to macOS and Windows.
- This UI demonstrates `smart_interface`, `font_size_pct`, `color_profile`, `letter_spacing_px`, `reduce_complexity`, and `target_size_pct`. It does **not** automatically adapt third-party applications or change native OS fonts.
- GazeControl, SteadyHand, and speech integrations remain independent. The demo retains `target_activated`, `mode_changed` and `demo_submitted` Qt signals for the team.
- The local appointment is fictional and no medical records are transmitted.
- On a laptop, two relatively wide windows might overlap. Move them between desktop spaces or displays, or resize to view them side by side. Form contents scroll when the window is narrow.

## Testing

```bash
source ~/.venvs/accessshift/bin/activate
python -m accessshift
# or optional Qt smoke test:
python scripts/test_smartinterface_live_preview.py
```

Do not merge before opening and checking both windows on the target macOS/Windows demo machines.
