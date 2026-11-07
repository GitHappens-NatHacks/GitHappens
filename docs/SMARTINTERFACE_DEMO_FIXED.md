# AccessShift AI — SmartInterface Demo Lab

## Purpose
A self-contained simulated healthcare booking form for natHacks 2026. No real patient data or external websites are involved. The AccessShift dashboard is separate.

## What the judge should see
1. Open **Test & preview → Open healthcare demo**.
2. Select **Original portal**. It displays small targets, distracting navigation, and a compact all-on-one-page form.
3. Type a fictional first name, select a department and choose **11:00 AM**.
4. Select **Apply SmartInterface**. It **does not open a different booking page**: the same controls and values are reorganized into clearer, larger steps, and sidebars disappear.
5. Proceed to **Review**. Verify that the name, department, reason and 11:00 AM selection are still there.
6. Switch back to **Original portal**. Confirm data is preserved.
7. Resize the window narrower. Dense mode gains a horizontal scrollbar instead of crushing form widgets; accessible mode flows inside a normal vertical scrolling area.

## Scope
- The transformation is deterministic, local, and rule-based — it demonstrates the intended adaptation behaviour, **not** AI-generated reformatting of arbitrary websites.
- All displayed medical information is fictional. Submitting a sample request does not send data.
- The same QLineEdit/QComboBox/QTextEdit widgets are reused in both modes. No duplicate state.
- Signals: `mode_changed(bool)`, `target_activated(str)`, `demo_submitted(object)`.
- `activate_target(target_id)` is a future integration point for gaze and stabilized pointer control.

## Fixes over the legacy Demo Lab
- Light-background/dark-text input styling, including multiline Reason field.
- Better contrast for labels, consent controls, time slots and action buttons.
- When resizing the window, inputs and sections remain accessible: QScrollArea with vertical and horizontal scrolling as needed.
- QScrollArea's content is assigned **after** its layout and child widgets are constructed.
- One real form is transformed rather than swapping two unrelated portals.

## Run tests
After installing and activating the team's Python environment:
`python scripts/test_smartinterface_demo.py`

This graphical smoke test verifies mode toggling, one shared form, data preservation, narrow-window scrolling and navigability. It must be run on a Mac or Windows installation with PySide6.
