# AccessShift SmartInterface — natHacks demo scope

## Included

- The **AccessShift desktop configuration application** (PySide6 on macOS / Windows).
- In-app visual customization: font scaling, theme choice, a letter-spacing preview, and an optional screen-colour tint.
- A **bundled, local healthcare appointment demonstration** using the existing `accessshift/ui/portal_view.py`.
- The healthcare demo is opened manually from **Test & preview → Open healthcare demo**.
- The original complicated workflow and the accessible workflow can be compared with two buttons.
- The initial demo mode follows the saved `smart_interface` preference.
- The local SteadyHand playground and integration hooks for gaze / speech remain in the application.

## Deliberately out of scope

- Chrome / Edge extensions, webpage CSS injection, and localhost browser-settings synchronization.
- Modification of Amazon, Google, or any other third-party site.
- Real healthcare bookings and actual patient data.
- Claims of universal, system-wide font replacement or fully automatic AI restructuring.

## Owner boundaries

- SmartInterface UI/demo: implement and compare supported local views.
- Gaze, SteadyHand, speech: other modules can use their own workers and integrate via existing control-center signals.
- PortalView remains team-owned and **is not overwritten** by this rollback.

## How to test

1. Start `python -m accessshift` in the established Python environment.
2. Open **Test & preview**, then **Open healthcare demo**.
3. Use **Original complex layout** / **Accessible SmartInterface layout**.
4. Close the demo; the accessibility configuration window stays open.
5. No browser installation is required.

## Technical note

The demo is a simulation. Although PortalView shows multiple choices and a booking button, it does not connect to an external booking service. It demonstrates an accessible layout rather than a production medical workflow. In-app visual preferences remain available independently of this demo.
