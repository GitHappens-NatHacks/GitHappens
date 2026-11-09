# Younify

Desktop accessibility tools for everyday healthcare workflows: pointer stabilization for tremor, head-and-blink hands-free control, and a calmer appointment form. Built for natHacks 2026 (Healthcare & Accessibility).

**Repo:** [GitHappens-NatHacks/GitHappens](https://github.com/GitHappens-NatHacks/GitHappens) · **App name in the UI:** Younify

---

## What it does

Younify is a PySide6 (Qt) app with a Control Center, a Demo Lab, and three main features:

| Feature | What you get |
| :--- | :--- |
| **SteadyHand** | Tremor filtering on a practice canvas, strength up to 200%, simulated tremor intensity, wider click zones, drag guard, session tremor chart, and trial export |
| **Head movement** | Webcam head pointing with a guided 5-step calibration, select by holding still (Relaxed, Normal or Quick) or by blinking, a full-screen hands-free booking demo with large photo targets, live camera preview, and on-screen alerts. Leave by closing your eyes for 5 seconds or with Quit hands-free |
| **SmartInterface** | Larger text, letter spacing, colour themes, screen tint, and a sample healthcare form that switches to a step-by-step layout |

Profiles (Steadier pointing, Hands-free control, Clearer interfaces, Custom mix) turn combinations of those modules on. Preferences save on the device.

Speech (offline TTS) and short word suggestions appear inside the hands-free keyboard path. They are not a separate Control Center tab.

---

## Tech stack

| Piece | Used for |
| :--- | :--- |
| Python 3.10–3.12 | App runtime (MediaPipe Face Mesh needs ≤3.12) |
| PySide6 | Control Center, Demo Lab, hands-free window |
| OpenCV + MediaPipe | Head pose, face landmarks, blink |
| Optional EyeTrax | Richer eye tracking when `GAZE_BACKEND=auto` / `eyetrax` / `hybrid` |
| pynput | Optional system pointer hooks for SteadyHand |
| pyttsx3 | Offline TTS in hands-free flows |
| onnxruntime | Optional local text prediction when enabled |

---

## Repository layout

```
GitHappens/
├── accessshift/              # Younify package
│   ├── __main__.py           # python -m accessshift
│   ├── app.py
│   ├── engine/               # Profiles + AdaptiveEngine
│   ├── modules/
│   │   ├── gaze/             # Tracking, blink, dwell, calibration
│   │   ├── steadyhand/       # Filter, hold, telemetry, targets
│   │   ├── smartinterface/   # Themes, tint, form modes
│   │   └── speech/           # TTS + optional prediction
│   └── ui/                   # Control Center, Demo Lab, gaze booking, SteadyHand panel
├── AccessShift_Extension/    # Standalone Chromium extension (reading, steady pointer); see its README
├── steadyhand_demo/          # SteadyHand practice targets and metrics
├── assets/
│   ├── brand/                # Logo and mark
│   ├── ui/                   # Photo headers
│   └── portal/               # Design references (live form is Qt)
├── docs/
├── scripts/                  # setup.sh, packaging helpers
├── tests/
├── requirements.txt
└── .env.example
```

---

## Demo flow

1. **SteadyHand:** Turn on simulated tremor, try Baseline vs Full assist, watch the session chart, export if needed.
2. **Head movement:** Start head control, follow the calibration arrows, then book an appointment by holding your head still on an option or blinking. Close your eyes for 5 seconds to leave.
3. **SmartInterface:** Open the Demo Lab healthcare form; toggle SmartInterface and reading settings and watch the form update.

---

## Prerequisites

- Python **3.10, 3.11, or 3.12** (3.13+ is not supported with the pinned MediaPipe build)
- Webcam for Head movement
- macOS: Camera permission for gaze; Accessibility if you use system-wide pointer control
- Windows: allow permission prompts on first run

---

## Setup

```bash
git clone https://github.com/GitHappens-NatHacks/GitHappens.git
cd GitHappens

python3.12 -m venv .venv          # or python3.11 / python3.10
source .venv/bin/activate         # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env              # optional camera / gaze backend tweaks
```

Or:

```bash
bash scripts/setup.sh
```

`setup.sh` picks a 3.10–3.12 interpreter, creates `.venv`, and copies `.env.example` when `.env` is missing.

---

## Run

```bash
source .venv/bin/activate
python -m accessshift
```

### Package (optional)

```bash
bash scripts/build_app.sh
```

Build on the OS you ship (Mac binary on Mac, Windows binary on Windows).

---

## Team

| Member | Focus |
| :--- | :--- |
| Adnan | Architecture, integration and UI |
| Pragati Puri | Head movement (head pointing, calibration, hands-free booking) |
| Yee | SteadyHand filters |
| Dipta | SteadyHand targets & metrics |
| Elizabeth | Healthcare form / SmartInterface |
| Avneet Kaur | Speech & predictive text |

## Credits

- MediaPipe Face Mesh (Google)
- 1-Euro filter (Casiez et al.)
- Qt / PySide6, OpenCV, pyttsx3, pynput, ONNX Runtime

## Known limitations

- Head tracking depends on lighting, camera angle, and calibration quality.
- Shipping pointing mode is **head**; eye pointing is experimental via env (`GAZE_BACKEND`, `GAZE_INPUT`).
- SteadyHand’s primary demo is the in-app canvas; system-wide pointer control needs OS Accessibility permission and is secondary.
- SmartInterface reshapes the bundled healthcare form. It does not restyle arbitrary third-party websites.
- ONNX text prediction is optional and off by default (`PREDICTION_ENABLED=0`).
- PyInstaller output must be built on the target OS.
