# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

People with motor impairments and related neurological conditions who struggle with dense healthcare UIs, tiny click targets, and pointer-dependent workflows. Profile modes currently center on ALS / severe motor impairment and Parkinson's / essential tremor; cognitive-accessibility profiles exist in the product plan as additional audiences.

## Product Purpose

AccessShift AI helps those users complete essential healthcare tasks (appointment booking and related portal flows) by adapting how they point, select, and see the interface. Success for the natHacks demo is completing booking scenarios hands-free or tremor-assisted with measurable gains in accuracy and task completion versus the unassisted cluttered portal.

## Positioning

An Adaptive Interaction Engine with per-profile customizable settings inside one desktop app: gaze/blink navigation, tremor-stabilized pointing, and interface simplification share one profile system. No specialty hardware is required today (webcam and OS permissions are enough). A lightweight browser extension is a planned companion surface. Future hardware (IR cameras for head movement and other sensors) is exploratory, not a current dependency.

## Operating Context

- Event and team context: natHacks 2026, Healthcare & Accessibility, Standard division; weekend demo and pitch.
- Primary client: PySide6 (Qt) desktop app on macOS and Windows (`python -m accessshift`). Impeccable's platform field has no desktop enum value; `web` is recorded for schema compliance while delivery remains native desktop. Browser-extension and future-hardware paths are secondary.
- Demo environment: built-in or USB webcam; macOS Camera and Accessibility permissions for gaze and SteadyHand; Windows permission prompts on first run.
- Core demo ritual: cluttered healthcare appointment booking inside the app, switched by profile between GazeControl, SmartInterface simplification, and SteadyHand assist.
- Packaging target: PyInstaller build for the demo laptop when ready.

## Capabilities and Constraints

Confirmed or in active build:

- Profile-driven Adaptive Interaction Engine (ALS, Parkinson's / tremor, cognitive, combined mixes).
- GazeControl: webcam gaze and blink/dwell selection (MediaPipe; EyeTrax hybrid path exists in the integrate line).
- SmartInterface: complex healthcare booking UI versus simplified step-by-step layout over bundled portal assets.
- SteadyHand: tremor smoothing and click assistance (in-app first; OS pointer when permissions allow).
- Speech / prediction: offline TTS (`pyttsx3`) and optional local/ONNX assist (partial).
- Planned product UI: a bookings history tab (all bookings so far) and a calendar view for those appointments.

Constraints and scope:

- SmartInterface targets the bundled healthcare demo first; arbitrary third-party sites are out of scope for the weekend.
- Gaze quality depends on lighting, camera angle, and calibration.
- Specialty hardware is out of scope for now; IR / additional sensors are future exploration only.
- Formal accessibility standard (e.g. WCAG level): undecided.

Undecided:

- Whether the browser extension ships in the same release train as the desktop app.
- Which IR or other hardware integrations land after the hackathon.

## Brand Commitments

- Product name: AccessShift AI.
- Repository / team name: GitHappens (natHacks).
- Voice and visual identity: not locked beyond the existing app UI; no separate brand book.

## Evidence on Hand

- README problem/solution copy, module table, demo scenarios, known limitations.
- `docs/milestones.md` weekend phases and pitch checklist.
- Bundled portal assets under `assets/portal/`.
- Demo / slides / video / Devpost links in README are placeholders; do not invent metrics, testimonials, or press.

## Product Principles

1. Adapt the interaction path to the person (profile), not force one input method on every user.
2. Prefer software and commodity cameras over specialty hardware until hardware is deliberately integrated.
3. Keep healthcare task completion (booking and follow-through) as the proof of value, including history and calendar of bookings.
4. Measure what the demo claims: accuracy, accidental clicks, time, and selection reliability.
5. Do not fabricate accessibility compliance claims while standards remain undecided.

## Accessibility & Inclusion

Primary audience needs motor-accessible input (gaze, blink/dwell, tremor smoothing, larger or simplified targets) and reduced cognitive load in portal flows. No formal standard (WCAG or similar) is committed yet.
