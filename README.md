# GitHappens

# AccessShift AI — Adaptive Digital Accessibility

> An AI-powered digital accessibility platform that dynamically reconstructs complex web interfaces and adapts interaction modes (webcam gaze, blink-to-speech, and tremor-stabilized mouse control) to individual physical abilities.

**Demo:** _link_ · **Slides:** _link_ · **Video:** _link_ · **Devpost:** _link_

---

## The Problem

Millions of people with motor disabilities, neurological conditions, and cognitive impairments face severe barriers when using standard digital interfaces. Essential tasks, such as booking medical appointments, managing prescriptions, and accessing records, are often built with dense forms, visual clutter, and tiny interactive targets.

Traditional accessibility tools typically rely on prohibitively expensive dedicated hardware (such as proprietary eye-trackers), complex manual configurations, or isolated single-purpose applications that fail to address diverse or overlapping motor and cognitive impairments.

---

## Our Solution

AccessShift AI transforms existing web applications into personalized, accessible experiences using standard consumer computer hardware. 

At the center of our solution is the **Adaptive Interaction Engine**. Instead of offering disconnected tools, AccessShift AI identifies a user's physical profile and activates an optimized combination of interface reorganization, alternative inputs, and real-time cursor assistance:

- **User with ALS / Quadriplegia:** Eye tracking + blink confirmation + predictive speech + simplified task interface.
- **User with Parkinson's / Essential Tremor:** Real-time tremor filtering + magnetic target enlargement + adaptive click assistance.
- **User with Cognitive Impairments:** Task-focused interface reconstruction + step-by-step guidance + reduced visual complexity.
- **User with Multi-Modal Needs:** Dynamic combinations of gaze navigation, simplified layouts, and assisted pointer controls.

---

## Three Integrated Accessibility Systems

### 1. GazeControl: Eye and Blink Navigation
- Uses a standard laptop webcam to track eye movements and intentional blinks.
- Enables hands-free web navigation without touching a mouse or keyboard.
- Features an eye-driven predictive keyboard with dynamic dwell times.
- Integrates AI text expansion and the Web Speech API (Text-to-Speech) for vocalization.
- Adjusts target button hitboxes based on gaze calibration stability.
- **Technologies:** Python, MediaPipe Face Mesh, OpenCV, JavaScript, Web Speech API, Local/Cloud LLM.

### 2. SmartInterface: AI Website Transformation
- Analyzes existing DOM trees and complex layouts.
- Reconstructs complicated workflows into simplified, task-focused screens.
- Enlarges interactive targets, clarifies instructions, and eliminates distracting sidebars.
- Exposes direct state hooks for hands-free gaze navigation and tremor-stabilized pointers.
- **Technologies:** React, Next.js, JavaScript, DOM analysis, Tailwind CSS, Accessibility heuristics.

### 3. SteadyHand: AI Tremor Stabilization
- Filters out high-frequency involuntary hand tremors in real time.
- Implements 1-Euro and adaptive exponential smoothing filters on raw cursor coordinates.
- Employs intelligent target snapping (bubble cursor logic) that dynamically enlarges clickable bounds as the pointer approaches.
- Minimizes false clicks and accidental double triggers.
- **Technologies:** JavaScript, 1-Euro filter algorithms, cursor trajectory modeling, proximity bounding box math.

---
## Tech Stack

| Component | Technology | Purpose |
| :--- | :--- | :--- |
| **Language** | Python 3.11+ | Single codebase for logic, vision, UI, and DSP |
| **Desktop UI Framework** | PySide6 (Qt) | Cross-platform desktop interface for macOS and Windows |
| **Computer Vision** | OpenCV + MediaPipe Face Mesh | Real-time iris tracking, gaze estimation, and blink detection |
| **Mouse Control** | pynput + OS Input APIs | Tremor filtering, cursor smoothing, and target proximity snapping |
| **Signal Processing** | 1-Euro Filter + NumPy | Real-time mathematical cancellation of involuntary hand tremors |
| **Speech & Audio** | pyttsx3 | Fast, offline, low-latency text-to-speech synthesis |
| **AI & Text Prediction** | ONNX Runtime / Lightweight Local Models | Next-word completion and message simplification |
| **Distribution** | PyInstaller | Standalone executable generation for Windows and macOS |
---

## Hackathon Demonstration Scenarios

We evaluate and demonstrate AccessShift AI on an intentionally cluttered healthcare appointment booking portal through three reproducible benchmarks:

1. **Scenario 1 (Gaze & Blink Control):** A user navigates the booking portal and completes an appointment entirely hands-free using webcam gaze tracking and deliberate blink confirmations.
2. **Scenario 2 (SmartInterface Transformation):** The original complex portal is transformed with a single toggle into a clear, high-contrast, linear step-by-step interface.
3. **Scenario 3 (SteadyHand Tremor Test):** A user navigates small appointment buttons while generating hand tremors (simulated via phone vibration). Turning on SteadyHand stabilizes the cursor and magnetically locks onto the target button, demonstrating clear before-and-after accuracy improvements.

### Measurable Verification Metrics
- Click accuracy (hits vs. misses) before and after SteadyHand activation.
- Accidental click reduction percentage.
- Task completion time across complex vs. simplified interface modes.
- Total interaction steps required to book an appointment.
- Gaze dwell and blink selection accuracy.

---

## Team & Responsibilities

| Team Member | Academic Level | Role | Core Responsibilities & Deliverables |
| :--- | :--- | :--- | :--- |
| **Adnan** | Last-year student | Technical Lead (Architecture & GazeControl) | Lead system architecture, MediaPipe Face Mesh gaze tracking, blink detection, and WebSocket integration between Python vision and the React frontend. |
| **Pragati Puri** | Third-year student | Technical Lead (Adaptive Engine & Dashboard) | Build the Adaptive Interaction Engine logic, user profile management (ALS, Parkinson's, Cognitive), and coordinate unified system state across modules. |
| **Yee** | Second-year student | Algorithm Developer (SteadyHand Core) | Research and implement 1-Euro filtering and adaptive smoothing algorithms to cancel cursor tremor jitter in JavaScript. |
| **Dipta** | Second-year student | Algorithm Developer (SteadyHand UX & Targets) | Implement magnetic cursor proximity snapping, adjustable stabilization sliders, and build the jitter benchmark testing suite. |
| **Elizabeth** | Second-year student | Frontend Lead (SmartInterface Portal) | Design and develop the complex healthcare booking portal mock, the simplified accessible layout, and DOM restructuring toggles. |
| **Avneet Kaur** | Second-year student | AI & Frontend Engineer (SmartInterface AI) | Implement accessible layout styling, Web Speech API integration, predictive text assistance, and LLM prompt design for text simplification. |

---

## Getting Started

### Prerequisites
- Node.js 18+ and npm
- Python 3.10+
- Built-in or USB webcam

### 1. Clone the Repository
```bash
git clone <repo-url>
cd AccessShift-AI
