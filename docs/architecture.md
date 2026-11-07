# AccessShift AI architecture (PySide6)

## Process model

```
python -m accessshift
  → QApplication
  → MainWindow
       ├── AdaptiveEngine (profiles → module flags)
       ├── PortalView (SmartInterface complex/accessible)
       ├── GazeTracker (OpenCV + MediaPipe)  [worker thread next]
       ├── SteadyHandController (1-Euro + optional pynput)
       └── SpeechEngine (pyttsx3 + suggest_words / ONNX)
```

## Module boundaries

| Module | Package | Side effects |
| :--- | :--- | :--- |
| Profiles / engine | `accessshift/engine` | Emits Qt signals when flags change |
| GazeControl | `accessshift/modules/gaze` | Camera capture, landmark math |
| SteadyHand | `accessshift/modules/steadyhand` | Filters coordinates; optional OS mouse |
| SmartInterface | `accessshift/ui/portal_view` + `modules/smartinterface` | Swaps portal layouts |
| Speech | `accessshift/modules/speech` | Offline TTS; optional ONNX rerank |

## Cross-platform notes

- Develop shared logic in Python first.
- Keep system-wide mouse moves behind `try_enable_system_mouse()`.
- Build PyInstaller artifacts on each OS separately.
