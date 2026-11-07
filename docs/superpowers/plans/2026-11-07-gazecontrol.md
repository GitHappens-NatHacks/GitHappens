# GazeControl Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let a user operate the AccessShift AI desktop app, book an appointment in the healthcare portal and speak a typed message, using only a laptop webcam (eye gaze plus deliberate blinks).

**Architecture:** This builds on the gaze scaffold already on `origin/main` (`accessshift/modules/gaze/`). Pure-Python logic modules (eye features, calibration fit, blink detection, dwell timing) have no Qt or camera dependency and are unit-tested. A `GazeWorker` runs the camera loop on a `QThread`. A `GazeController` (QObject) turns samples into a smoothed screen point, hit-tests the widget under it, and clicks it on a dwell or a deliberate blink. The UI adds a full-screen calibration dialog, a gaze cursor overlay and a gaze keyboard. `MainWindow` only starts and stops the controller when the `gaze_control` module flag changes.

**Tech Stack:** Python 3.11+, PySide6, OpenCV, MediaPipe Face Mesh (`refine_landmarks=True`), NumPy, pyttsx3, pytest.

**Spec:** `README.md` → "1. GazeControl: Eye and Blink Navigation" and "Hackathon Demonstration Scenarios → Scenario 1", plus `docs/demo-script.md` (2:50–4:10) on `origin/main`.

## Global Constraints

- **Step 0, before Task 1:** your branch must contain the `main` scaffold. Run `git merge origin/main` on `GazeControl` (it should fast-forward). Without it, none of the files below exist.
- Hardware: a standard built-in or USB webcam only. No dedicated eye tracker.
- Camera index comes from env `GAZE_CAMERA_INDEX` (default `0`), already in `.env.example` on main.
- Use `OneEuroFilter` from `accessshift/modules/steadyhand/filter.py` for smoothing. Don't write a second filter. Its timestamps are in **seconds**.
- Use `suggest_words(prefix, limit)` from `accessshift/modules/speech/predict.py` and `SpeechEngine.speak(text)` from `accessshift/modules/speech/tts.py`. LLM text completion is out of scope for this plan.
- Logic modules (`features.py`, `calibration.py`, `blink.py`, `dwell.py`) must not import PySide6, cv2 or mediapipe.
- All timestamps inside the gaze package are integer **milliseconds** (`ts_ms`), except when calling `OneEuroFilter`.
- Qt tests run headless: `QT_QPA_PLATFORM=offscreen`.
- Coordinate with teammates: `origin/feature/healthcare-portal-ui` rewrites `main_window.py` into a control center. Keep the `MainWindow` changes in Task 7 under ~20 lines so they're easy to move.

## Review Focus

1. **Natural blinks clicking things.** People blink 15–20 times a minute (~100–150 ms each). Only closures of 300–1500 ms count as a selection. → test `test_natural_blink_ignored` in Task 2.
2. **Eyes closed to rest.** Holding the eyes shut for several seconds must not select anything. → test `test_long_closure_ignored` in Task 2.
3. **Face leaves the frame or the camera fails.** The cursor freezes, dwell resets and nothing gets clicked, and the status line says why. → test `test_no_face_resets_dwell` in Task 5.
4. **Staring at one button.** It fires once, then must not fire again until gaze leaves and comes back. Otherwise an ALS user books twice. → test `test_fires_once_until_reentry` in Task 4.
5. **Gaze lands off-screen or on a non-button.** Points are clamped to the screen, and only enabled `QAbstractButton`s get clicked. → test `test_only_enabled_buttons_clicked` in Task 5.

Known risk, not tested: `SpeechEngine.speak()` calls `runAndWait()`, which blocks the UI thread. Task 6 runs it on a worker thread.
Known risk: newer MediaPipe releases may drop the legacy `mp.solutions.face_mesh` API. In Task 2, check that `python -c "import mediapipe as mp; mp.solutions.face_mesh"` works, and pin the installed version in `requirements.txt` if it does.

---

### Task 1: Eye features (iris position within the eye)

The scaffold uses the iris position in the camera frame, which mostly measures head position. Use the iris position *relative to the eye corners* instead.

**Files:**
- Create: `accessshift/modules/gaze/features.py`
- Create: `tests/__init__.py`, `tests/gaze/__init__.py`, `tests/gaze/test_features.py`
- Create: `requirements-dev.txt` (contents: `pytest>=8`)

**Interfaces:**
- Produces:
  - Constants `LEFT_EYE`, `RIGHT_EYE`, `LEFT_IRIS`, `RIGHT_IRIS` (moved from `tracker.py`, same values)
  - `Point = tuple[float, float]`
  - `iris_ratio(corner_a: Point, corner_b: Point, iris: Point) -> Point`: `u` = projection of `iris - corner_a` onto the corner axis divided by |axis|² (0 at `corner_a`, 1 at `corner_b`); `v` = signed perpendicular offset divided by |axis| (positive = down in image coordinates).
  - `gaze_feature(points: Sequence[Point]) -> Point`: `points` are pixel coordinates indexed by mesh landmark id. Returns the mean of `iris_ratio` for both eyes, with corners `LEFT_EYE[0]`/`LEFT_EYE[3]` and `RIGHT_EYE[0]`/`RIGHT_EYE[3]`, and the iris centre = mean of the iris landmarks.

- [ ] **Step 1: Write failing tests**

```python
def test_iris_centered():
    assert iris_ratio((0, 0), (10, 0), (5, 0)) == pytest.approx((0.5, 0.0))

def test_iris_toward_corner_b_and_down():
    u, v = iris_ratio((0, 0), (10, 0), (8, 2))
    assert u == pytest.approx(0.8) and v == pytest.approx(0.2)

def test_translation_invariant():
    a = iris_ratio((0, 0), (10, 0), (3, 1))
    b = iris_ratio((100, 50), (110, 50), (103, 51))
    assert a == pytest.approx(b)

def test_zero_width_eye_returns_center():
    assert iris_ratio((5, 5), (5, 5), (5, 5)) == (0.5, 0.0)
```

- [ ] **Step 2: Run** `pytest tests/gaze/test_features.py -v`. Expected: FAIL (module not found).
- [ ] **Step 3: Implement** `features.py` using the interface above.
- [ ] **Step 4: Run** `pytest tests/gaze/test_features.py -v`. Expected: 4 passed.
- [ ] **Step 5: Commit** `feat(gaze): eye-relative iris features`

---

### Task 2: Time-based deliberate blink detection, plus tracker update

**Files:**
- Modify: `accessshift/modules/gaze/blink.py` (replace the frame-count logic)
- Modify: `accessshift/modules/gaze/tracker.py` (use `features.py`, new blink API, remove single-point `calibrate()`/`_origin`)
- Test: `tests/gaze/test_blink.py`

**Interfaces:**
- Consumes: `features.LEFT_EYE`, `RIGHT_EYE`, `gaze_feature`
- Produces:
  - `eye_aspect_ratio(eye) -> float` (unchanged)
  - `BlinkDetector(ear_threshold: float = 0.21, min_ms: int = 300, max_ms: int = 1500, cooldown_ms: int = 500)`
  - `BlinkDetector.update(ear: float, ts_ms: int) -> bool`: True on the frame the eye **reopens** after a closure lasting `min_ms ≤ duration ≤ max_ms`, and not within `cooldown_ms` of the last True.
  - `BlinkDetector.calibrate_open(ears: list[float]) -> None`: sets `ear_threshold = 0.75 * median(ears)`. Ignores an empty list.
  - `GazeTracker.read() -> dict | None` payload keys: `camera_ok: bool`, `face: bool`, `ts_ms: int`, `frame` (BGR ndarray), and when `face` is True also `feature: Point`, `ear: float`, `blink: bool`.

- [ ] **Step 1: Write failing tests.** Helper `feed(det, [(ear, ts_ms), ...]) -> list[bool]`.

```python
def test_deliberate_blink_fires_on_reopen():
    d = BlinkDetector()
    out = feed(d, [(0.3, 0), (0.1, 100), (0.1, 300), (0.1, 500), (0.3, 520)])
    assert out == [False, False, False, False, True]

def test_natural_blink_ignored():           # ~120 ms closure
    d = BlinkDetector()
    assert not any(feed(d, [(0.3, 0), (0.1, 100), (0.1, 180), (0.3, 220)]))

def test_long_closure_ignored():            # eyes resting for 3 s
    d = BlinkDetector()
    assert not any(feed(d, [(0.3, 0), (0.1, 100), (0.1, 3100), (0.3, 3150)]))

def test_cooldown_blocks_second_blink():
    d = BlinkDetector()
    out = feed(d, [(0.1, 0), (0.3, 400), (0.1, 450), (0.3, 850)])
    assert out == [False, True, False, False]

def test_calibrate_open_sets_threshold():
    d = BlinkDetector(); d.calibrate_open([0.30, 0.32, 0.28])
    assert d.ear_threshold == pytest.approx(0.225)
```

- [ ] **Step 2: Run** `pytest tests/gaze/test_blink.py -v`. Expected: FAIL.
- [ ] **Step 3: Implement** the new `BlinkDetector`. Track `closed_since_ms`; measure the duration when EAR rises back above the threshold.
- [ ] **Step 4: Update** `tracker.py`: build `points` for all 478 landmarks once per frame, call `gaze_feature(points)`, compute the mean EAR of both eyes, call `self.blink.update(ear, ts_ms)`. Use `ts_ms = int(time.monotonic() * 1000)` (not wall clock). Update `gaze/__init__.py` exports if names change.
- [ ] **Step 5: Run** `pytest tests/gaze -v` (all pass), then a manual camera check: `python -c "from accessshift.modules.gaze import GazeTracker as T; t=T(); t.open(); import time; [print(t.read().get('feature'), t.read().get('blink')) or time.sleep(0.1) for _ in range(30)]; t.close()"`. Expected: features change as you look left/right, and a ~0.5 s blink prints `True`. Also run the MediaPipe import check from Review Focus.
- [ ] **Step 6: Commit** `feat(gaze): time-based deliberate blink + eye-relative tracker`

---

### Task 3: Calibration fit (feature → screen pixels)

**Files:**
- Create: `accessshift/modules/gaze/calibration.py`
- Test: `tests/gaze/test_calibration.py`

**Interfaces:**
- Produces:
  - `CALIBRATION_POINTS: list[Point]` = the 9 normalized points `(x, y)` for x, y ∈ {0.1, 0.5, 0.9}, in row-major order
  - `class GazeCalibration` with:
    - `fit(features: list[Point], targets: list[Point]) -> None`: least-squares fit of a 2nd-order polynomial per axis, terms `[1, u, v, u·v, u², v²]` (`numpy.linalg.lstsq`). Raises `ValueError` if fewer than 6 pairs or the lengths differ.
    - `is_fitted: bool` (property)
    - `map(feature: Point) -> Point`: screen pixels, not clamped. Raises `RuntimeError` if not fitted.
    - `error_px(features: list[Point], targets: list[Point]) -> float`: mean Euclidean distance between `map(f)` and the target

- [ ] **Step 1: Write failing tests.**

```python
def test_recovers_affine_mapping():
    feats = [(u, v) for u in (0.3, 0.5, 0.7) for v in (-0.1, 0.0, 0.1)]
    targets = [(1000 * u + 50, 2000 * v + 400) for u, v in feats]
    c = GazeCalibration(); c.fit(feats, targets)
    assert c.map((0.6, 0.05)) == pytest.approx((650, 500), abs=1e-6)
    assert c.error_px(feats, targets) == pytest.approx(0, abs=1e-6)

def test_too_few_points_raises():
    with pytest.raises(ValueError):
        GazeCalibration().fit([(0, 0)] * 5, [(0, 0)] * 5)

def test_map_before_fit_raises():
    with pytest.raises(RuntimeError):
        GazeCalibration().map((0.5, 0.0))

def test_nine_points():
    assert len(CALIBRATION_POINTS) == 9 and CALIBRATION_POINTS[0] == (0.1, 0.1)
```

- [ ] **Step 2: Run** `pytest tests/gaze/test_calibration.py -v`. Expected: FAIL.
- [ ] **Step 3: Implement** `calibration.py`.
- [ ] **Step 4: Run** the same command. Expected: 4 passed.
- [ ] **Step 5: Commit** `feat(gaze): 9-point polynomial calibration`

---

### Task 4: Dwell selection and adaptive sizing

**Files:**
- Create: `accessshift/modules/gaze/dwell.py`
- Test: `tests/gaze/test_dwell.py`

**Interfaces:**
- Produces:
  - `@dataclass DwellState: target: Hashable | None; progress: float; fired: bool`
  - `DwellSelector(dwell_ms: int = 1000)` with:
    - `update(target: Hashable | None, ts_ms: int) -> DwellState`. Progress goes 0→1 over `dwell_ms` while `target` stays the same. `fired=True` on exactly one update, when progress reaches 1. After that the same target never fires again until `target` changes (re-entry re-arms it). `None` resets everything.
    - `reset() -> None`
  - `adaptive_dwell_ms(error_px: float) -> int` = `clamp(round(800 + 4 * error_px), 600, 2000)`
  - `min_target_px(error_px: float) -> int` = `max(64, ceil(2 * error_px))`

- [ ] **Step 1: Write failing tests.**

```python
def test_fires_after_dwell():
    d = DwellSelector(1000)
    assert d.update("a", 0).progress == 0
    assert d.update("a", 500).progress == pytest.approx(0.5)
    assert d.update("a", 1000).fired

def test_fires_once_until_reentry():
    d = DwellSelector(1000); d.update("a", 0); d.update("a", 1000)
    assert not d.update("a", 3000).fired
    d.update("b", 3100); d.update("a", 3200)
    assert d.update("a", 4200).fired

def test_target_change_resets_progress():
    d = DwellSelector(1000); d.update("a", 0); d.update("a", 900)
    assert d.update("b", 950).progress == 0

def test_adaptive_values():
    assert adaptive_dwell_ms(0) == 800 and adaptive_dwell_ms(500) == 2000
    assert adaptive_dwell_ms(-100) == 600
    assert min_target_px(10) == 64 and min_target_px(50) == 100
```

- [ ] **Step 2: Run** `pytest tests/gaze/test_dwell.py -v`. Expected: FAIL.
- [ ] **Step 3: Implement** `dwell.py`.
- [ ] **Step 4: Run** the same command. Expected: 4 passed.
- [ ] **Step 5: Commit** `feat(gaze): dwell selector with adaptive timing`

---

### Task 5: Camera worker thread and GazeController

**Files:**
- Create: `accessshift/modules/gaze/worker.py`
- Create: `accessshift/modules/gaze/controller.py`
- Test: `tests/gaze/test_controller.py` (uses `QApplication` with offscreen platform via a module-level fixture)

**Interfaces:**
- Consumes: `GazeTracker.read()` payload (Task 2), `GazeCalibration` (Task 3), `DwellSelector`, `adaptive_dwell_ms` (Task 4), `OneEuroFilter`
- Produces:
  - `GazeWorker(QObject)`, constructed with `tracker_factory: Callable[[], GazeTracker]`. Signals `sample(dict)` and `error(str)`. Slots `run()` (loop until `stop()`, ~30 fps, emits `error` and returns if `open()` fails) and `stop()`. The `frame` key is dropped before emitting, except when `preview=True`.
  - `GazeController(QObject)`, constructed with `hit_test: Callable[[QPoint], QWidget | None]` (default `QApplication.widgetAt`) and `screen_rect: QRect`. It has:
    - Signals: `point(QPoint)`, `dwell(float)` (0–1), `selected(QWidget)`, `status(str)`
    - `calibration: GazeCalibration` attribute. `set_calibration(cal, error_px)` sets it and also sets `dwell_ms = adaptive_dwell_ms(error_px)`.
    - `process(sample: dict) -> None` (the testable core):
      1. If `not face`: emit `status("Face not found — look at the camera")`, reset dwell, return.
      2. Map the feature through the calibration, apply a One-Euro filter per axis (`min_cutoff=1.0, beta=0.01`), clamp to `screen_rect`, emit `point`.
      3. `w = hit_test(pt)`. Walk up parents to the first `QAbstractButton`. Use it only if it is enabled and visible, otherwise `None`.
      4. Update the dwell with that widget and emit `dwell(progress)`. If `fired` or (`sample["blink"]` and the widget is not None): call `w.click()`, emit `selected(w)`, `reset()` the dwell.
    - `start(camera_index: int)` / `stop()`: own the `QThread` + `GazeWorker`, connect `sample → process`. `stop()` must join the thread.
  - Feature rule: if the calibration isn't fitted, `process` emits `status("Calibrate first")` and does nothing else.

- [ ] **Step 1: Write failing tests.** Use a fitted calibration where feature == screen px (fit identity on a 3×3 grid). Use a `hit_test` lambda returning a real `QPushButton` (counting clicks via `clicked.connect`) or `None`. Feed samples like `{"face": True, "feature": (100, 100), "blink": False, "ts_ms": t}`.

```python
def test_dwell_clicks_button(ctrl, button): ...       # 1000 ms on the button -> clicks == 1
def test_blink_clicks_immediately(ctrl, button): ...  # one sample with blink=True -> clicks == 1
def test_no_face_resets_dwell(ctrl, button): ...      # 600 ms on, a no-face sample, 600 ms on -> clicks == 0
def test_only_enabled_buttons_clicked(ctrl, button):  # button.setEnabled(False); dwell 1000 ms -> clicks == 0; QLabel target -> no click
def test_point_clamped_to_screen(ctrl): ...           # feature (-500, 99999) -> emitted point inside screen_rect
def test_uncalibrated_does_nothing(): ...             # status == "Calibrate first", no point emitted
```

- [ ] **Step 2: Run** `QT_QPA_PLATFORM=offscreen pytest tests/gaze/test_controller.py -v`. Expected: FAIL.
- [ ] **Step 3: Implement** `worker.py` and `controller.py`.
- [ ] **Step 4: Run** the same command. Expected: 6 passed. Then `pytest tests -v`: everything passes.
- [ ] **Step 5: Commit** `feat(gaze): threaded worker and gaze controller`

---

### Task 6: Calibration dialog, gaze overlay and gaze keyboard

These are UI tasks, verified manually with the camera.

**Files:**
- Create: `accessshift/ui/gaze_calibration_dialog.py`
- Create: `accessshift/ui/gaze_overlay.py`
- Create: `accessshift/ui/gaze_keyboard.py`

**Interfaces:**
- Consumes: `GazeController` (Task 5), `CALIBRATION_POINTS`, `GazeCalibration`, `BlinkDetector.calibrate_open`, `min_target_px`, `suggest_words`, `SpeechEngine`
- Produces:
  - `GazeCalibrationDialog(QDialog)`, constructed with `controller`. It is full screen and shows one 40 px dot at a time from `CALIBRATION_POINTS`. For each dot it waits 500 ms to settle, then collects samples for 1000 ms and uses their median feature (skipping no-face samples). It collects EAR samples throughout for `calibrate_open`. After the 9 points it runs a validation pass on the 4 points `(0.3,0.3) (0.7,0.3) (0.3,0.7) (0.7,0.7)`, computes `error_px`, calls `controller.set_calibration(cal, err)`, and shows "Accuracy: ±N px". `Esc` cancels. While the dialog is open, the controller's click handling is paused (`controller.paused = True`).
  - `GazeOverlay(QWidget)`: frameless, translucent, transparent to mouse input, always on top, full screen. It draws a 24 px dot at `point` and a ring that fills with `dwell` progress.
  - `GazeKeyboard(QWidget)`, constructed with `speech: SpeechEngine` and `error_px: float`:
    - Rows: 5 suggestion buttons from `suggest_words(current_word)`, then letters A–Z in rows of 7, then `Space`, `⌫`, `Clear`, `Speak`.
    - Every key's minimum size is `min_target_px(error_px)` × same.
    - A text field shows the message. Picking a suggestion replaces the current word and adds a space.
    - `Speak` calls `speech.speak(text)` on a `QThreadPool` worker, so the UI doesn't freeze.

- [ ] **Step 1:** Build the calibration dialog. Manual check: run it, follow the dots. The accuracy label shows a number, and the gaze dot then roughly follows your eyes (within ~150 px on a laptop screen).
- [ ] **Step 2:** Build the overlay. Manual check: the dot follows gaze, the ring fills while looking at a button, and mouse clicks still pass through to the app beneath.
- [ ] **Step 3:** Build the keyboard. Manual check: type "app", pick the "appointment" suggestion, press Speak. You hear speech and the UI stays responsive while it speaks.
- [ ] **Step 4:** Add a smoke test `tests/gaze/test_keyboard.py::test_suggestion_replaces_word` (offscreen). Set the text to `"book app"`, click the first suggestion. The text is now `"book appointment "`. Run `QT_QPA_PLATFORM=offscreen pytest tests -v`: all pass.
- [ ] **Step 5: Commit** `feat(gaze): calibration dialog, overlay, keyboard`

---

### Task 7: Wire into MainWindow, adaptive targets and metrics

**Files:**
- Modify: `accessshift/ui/main_window.py` (or whichever window file is current after the portal-UI branch merges)
- Create: `accessshift/modules/gaze/metrics.py`
- Test: `tests/gaze/test_metrics.py`
- Modify: `docs/milestones.md` (tick the Phase 2 and Phase 3 gaze items)

**Interfaces:**
- Consumes: everything above. Engine signal `modules_changed(ModuleFlags)` and `modules.gaze_control`.
- Produces:
  - `GazeMetrics` with `record_selection(ts_ms: int, intended: str | None, actual: str) -> None`, `start_task(ts_ms)`, `end_task(ts_ms)`, and `summary() -> dict` with keys `selections`, `accuracy` (correct / selections that have an intended value, or `None`), `task_ms`.
  - In `MainWindow`:
    - When `gaze_control` turns on: start the controller with `int(os.getenv("GAZE_CAMERA_INDEX", "0"))`, show the overlay, open the calibration dialog if not calibrated.
    - When it turns off: `stop()` the controller and hide the overlay.
    - Add buttons "Recalibrate gaze" and "Gaze keyboard".
    - Route `controller.status` into the existing `self.status` label.
    - Stop the controller in `closeEvent`.

- [ ] **Step 1: Write failing tests** for `GazeMetrics`:

```python
def test_accuracy_and_time():
    m = GazeMetrics(); m.start_task(0)
    m.record_selection(100, "Neurology", "Neurology")
    m.record_selection(200, "Tue 10:00", "Tue 10:30")
    m.record_selection(300, None, "Book appointment")
    m.end_task(5000)
    assert m.summary() == {"selections": 3, "accuracy": 0.5, "task_ms": 5000}

def test_empty_summary():
    assert GazeMetrics().summary() == {"selections": 0, "accuracy": None, "task_ms": None}
```

- [ ] **Step 2: Run** `pytest tests/gaze/test_metrics.py -v`. Expected: FAIL. **Step 3:** Implement. **Step 4:** Run again. Expected: 2 passed.
- [ ] **Step 5:** Wire `MainWindow` as described. Connect `controller.selected` to a metrics call that logs `button.text()`.
- [ ] **Step 6: End-to-end demo check (Scenario 1).**
  1. Run `python -m accessshift` and select the ALS profile. GazeControl turns on and calibration opens.
  2. Finish calibration.
  3. With hands off the keyboard and mouse, book an appointment in the accessible portal using dwell and blinks.
  4. Open Gaze keyboard, type "confirm", press Speak.

  Expected: booking completes and speech plays. Write down the accuracy (±px), selections and task time for the pitch slides.
- [ ] **Step 7:** Run `QT_QPA_PLATFORM=offscreen pytest tests -v`: all pass. Update `docs/milestones.md`.
- [ ] **Step 8: Commit** `feat(gaze): integrate GazeControl into main window with metrics`
