# AccessShift AI (GitHappens)

> Adaptive digital accessibility for healthcare workflows: webcam gaze/blink navigation, AI interface simplification, and tremor-stabilized mouse control in one cross-platform desktop app.

**Event:** natHacks 2026 · **Division:** Standard · **Theme:** Healthcare & Accessibility  
**Demo:** _link_ · **Slides:** _link_ · **Video:** _link_ · **Devpost:** _link_

---

## The Problem

Essential healthcare tasks (booking appointments, managing prescriptions, accessing records) often use dense forms, visual clutter, and tiny targets. People with motor disabilities, neurological conditions, or cognitive impairments hit hard barriers. Traditional tools need expensive hardware or one-off apps that do not cover overlapping needs.

## Our Solution

**AccessShift AI** is a Python desktop application that adapts interaction and interface to each user through an **Adaptive Interaction Engine**:

| Profile | Active modules |
| :--- | :--- |
| ALS / severe motor impairment | GazeControl + blink select + predictive speech + SmartInterface |
| Parkinson's / essential tremor | SteadyHand + target enlargement + click assistance |
| Cognitive accessibility | SmartInterface + step-by-step guidance + reduced complexity |
| Combined needs | Profile-selected mix of the above |

### Modules

1. **GazeControl** — Webcam eye/blink navigation (OpenCV + MediaPipe Face Mesh)
2. **SmartInterface** — Complicated healthcare booking UI ↔ simplified task layout
3. **SteadyHand** — 1-Euro / adaptive smoothing via `pynput` (in-app first, OS pointer next)
4. **Speech & prediction** — Offline TTS (`pyttsx3`) + optional local/ONNX text prediction

---

## Tech stack

| Component | Technology | Purpose |
| :--- | :--- | :--- |
| Programming language | Python 3.11+ | Main application logic and algorithms |
| Desktop framework | PySide6 (Qt) | Cross-platform graphical interface (macOS + Windows) |
| Computer vision | OpenCV + MediaPipe | Webcam tracking, gaze estimation, blink detection |
| AI | ONNX Runtime or local models | Text prediction and adaptive algorithms |
| Text-to-speech | pyttsx3 | Offline speech output |
| Mouse control | pynput + OS-specific APIs | Tremor filtering and mouse interactions |
| Packaging | PyInstaller | Distribute Windows and macOS applications |

**Why this stack:** one language for vision, DSP, UI, and speech; system-level pointer control that a browser extension cannot match; the same codebase on Mac and Windows; offline-friendly demos when the network is unreliable.

---

## Repository layout

```
GitHappens/
├── accessshift/                 # PySide6 application package
│   ├── __main__.py              # python -m accessshift
│   ├── app.py                   # QApplication bootstrap
│   ├── ui/                      # Main window, dashboard, portal views
│   ├── engine/                  # Profiles + Adaptive Interaction Engine
│   └── modules/
│       ├── gaze/                # MediaPipe gaze + blink
│       ├── steadyhand/          # 1-Euro filter + pynput controller
│       ├── speech/              # pyttsx3 + text prediction hooks
│       └── smartinterface/      # Complex ↔ accessible portal modes
├── assets/portal/               # Local healthcare booking demo pages
├── docs/                        # Architecture, milestones, demo script
├── scripts/                     # Setup + PyInstaller helpers
├── requirements.txt
└── .env.example
```

| Area | Owner (team plan) |
| :--- | :--- |
| Architecture, GazeControl, packaging | Adnan |
| Adaptive Engine + dashboard UI | Pragati |
| SteadyHand filters | Yee |
| SteadyHand targets / metrics | Dipta |
| Healthcare portal / SmartInterface UI | Elizabeth |
| Speech, prediction, ONNX/LLM assist | Avneet |

---

## Demo scenarios (judging)

Built around an intentionally cluttered healthcare appointment-booking flow inside the desktop app:

1. **Gaze & blink:** Complete booking hands-free with webcam gaze + blink confirm.
2. **SmartInterface:** Toggle complex layout → simplified step-by-step flow.
3. **SteadyHand:** Before/after click accuracy with simulated tremor, then live smoothing.

**Metrics:** click accuracy, accidental clicks, task time, interaction count, gaze selection accuracy.

---

## Prerequisites

- Python 3.11+
- Built-in or USB webcam
- macOS: grant **Camera** and **Accessibility** permissions when prompted (SteadyHand / gaze)
- Windows: run once so OS permission prompts can appear

### Optional
- ONNX model files under `assets/models/` when text prediction is enabled
- PyInstaller (for packaging builds)

## Setup

```bash
git clone https://github.com/GitHappens-NatHacks/GitHappens.git
cd GitHappens
cp .env.example .env

python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Or run `bash scripts/setup.sh`.

## Run

```bash
source .venv/bin/activate
python -m accessshift
```

### Package (later)

```bash
bash scripts/build_app.sh
```

Builds a platform binary with PyInstaller (run on each OS you ship).

---

## Priority for the weekend

1. PySide6 shell + profile dashboard  
2. Healthcare portal (complex + accessible) inside the app  
3. SteadyHand smoothing + click metrics  
4. GazeControl dwell / blink select  
5. pyttsx3 + predictive text if time remains  
6. PyInstaller pass for the demo machine  

Three working demos beat six half-finished features.

---

## Submission notes (natHacks)

- Code developed during the Nov 6–9, 2026 window  
- Submit by **Nov 9, 11:00 AM MDT**  
- README must explain how to run the demo  
- 5-minute pitch + demo, then 5-minute Q&A  

---

## Team

| Member | Role |
| :--- | :--- |
| Adnan | Architecture & GazeControl |
| Pragati Puri | Adaptive Engine & Dashboard |
| Yee | SteadyHand core filters |
| Dipta | SteadyHand targets & metrics |
| Elizabeth | Healthcare portal / SmartInterface UI |
| Avneet Kaur | Speech, predictive text, ONNX assist |

## Credits

- MediaPipe Face Mesh (Google)
- 1-Euro filter (Casiez et al.)
- Qt / PySide6, OpenCV, pyttsx3, pynput, ONNX Runtime

## Known limitations

- Gaze accuracy depends on lighting, camera angle, and calibration.
- macOS Accessibility permission is required for system-wide pointer control; in-app smoothing works without it.
- SmartInterface targets the bundled healthcare demo first; arbitrary third-party sites are out of scope for the weekend.
- ONNX text prediction is optional; core demos run offline with rule-based suggestions + pyttsx3.
- PyInstaller builds must be produced on the target OS (Mac build on Mac, Windows build on Windows).
