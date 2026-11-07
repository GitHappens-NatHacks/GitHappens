"""Full-screen GazeControl demo: 9-dot calibration, then a live gaze dot.

Run from the repo root:  python scripts/gaze_live.py
  SPACE  start calibration (keep your head still, follow each dot with your eyes)
  R      recalibrate
  Q/Esc  quit
After calibration, look at a box and do a slow (~half second) blink to select it.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
import json
import time
from statistics import median, pstdev

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from accessshift.modules.gaze import GazeTracker  # noqa: E402
from accessshift.modules.gaze.calibration import CALIBRATION_POINTS, GazeCalibration  # noqa: E402
from accessshift.modules.gaze.dwell import DwellSelector, adaptive_dwell_ms  # noqa: E402
from accessshift.modules.steadyhand.filter import OneEuroFilter  # noqa: E402

WINDOW = "AccessShift GazeControl"
VALIDATION_POINTS = [(0.3, 0.3), (0.7, 0.3), (0.3, 0.7), (0.7, 0.7)]
SETTLE_MS, COLLECT_MS, MIN_SAMPLES = 500, 1000, 5
MAX_SPREAD = 0.01  # eye-feature std above this means the eyes moved: redo the dot
BG, FG, ACCENT, OK, WARN = (24, 24, 28), (235, 235, 235), (0, 200, 255), (90, 210, 120), (60, 60, 230)


def screen_size() -> tuple[int, int]:
    """Logical size of the main screen. Asked in a subprocess so Qt and OpenCV windows don't clash."""
    override = os.getenv("GAZE_SCREEN")  # e.g. GAZE_SCREEN=1440x900
    if override:
        w, h = override.lower().split("x")
        return int(w), int(h)
    code = (
        "from PySide6.QtGui import QGuiApplication; a=QGuiApplication([]); "
        "s=a.primaryScreen().size(); print(s.width(), s.height())"
    )
    try:
        out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=15)
        w, h = out.stdout.split()[-2:]
        return int(w), int(h)
    except Exception:
        return 1440, 900


def text(img, msg, org, scale=0.8, color=FG, thick=2):
    cv2.putText(img, msg, org, cv2.FONT_HERSHEY_SIMPLEX, scale, color, thick, cv2.LINE_AA)


class PointCollector:
    """Shows one dot, waits SETTLE_MS, then gathers COLLECT_MS of open-eye samples."""

    def __init__(self, points, size):
        self.points, self.size = points, size
        self.index, self.started, self.samples = 0, None, []
        self.features: list = []
        self.ears: list = []
        self.debug: list = []  # per-dot sample count, spread, retries (for logs/)
        self.retries = 0

    @property
    def done(self) -> bool:
        return self.index >= len(self.points)

    def target_px(self, i=None):
        x, y = self.points[self.index if i is None else i]
        return (x * self.size[0], y * self.size[1])

    def update(self, sample, ear_threshold) -> None:
        ts = sample["ts_ms"]
        if self.started is None:
            self.started = ts
        elapsed = ts - self.started
        if elapsed >= SETTLE_MS and sample.get("face") and sample["ear"] >= ear_threshold:
            self.samples.append(sample["feature"])
            self.ears.append(sample["ear"])
        if elapsed >= SETTLE_MS + COLLECT_MS:
            steady = len(self.samples) >= MIN_SAMPLES and max(
                pstdev(s[0] for s in self.samples), pstdev(s[1] for s in self.samples)) <= MAX_SPREAD
            if steady:
                self.features.append((median(s[0] for s in self.samples), median(s[1] for s in self.samples)))
                self.debug.append({
                    "target_norm": self.points[self.index],
                    "samples": len(self.samples),
                    "std_u": pstdev(s[0] for s in self.samples),
                    "std_v": pstdev(s[1] for s in self.samples),
                    "retries": self.retries,
                })
                self.index += 1
                self.retries = 0
            else:
                self.retries += 1
            self.started, self.samples = None, []  # too few or unsteady samples: repeat this dot

    def draw(self, img, title, ts_ms):
        elapsed = 0 if self.started is None else max(0, ts_ms - self.started)
        x, y = map(int, self.target_px())
        shrink = 1.0 - min(1.0, max(0.0, (elapsed - SETTLE_MS) / COLLECT_MS))
        cv2.circle(img, (x, y), int(10 + 20 * shrink), ACCENT, 2, cv2.LINE_AA)
        cv2.circle(img, (x, y), 8, ACCENT, -1, cv2.LINE_AA)
        text(img, f"{title}: dot {self.index + 1} of {len(self.points)} - look at the dot, keep your head still",
             (40, 50))
        if self.retries:
            text(img, "Hold your eyes still on the dot - trying again", (40, 90), 0.8, WARN)



def save_debug(calib_c, valid_c, calib, error_px, ear_threshold, size) -> Path:
    """Write one calibration run to logs/ (git-ignored) for debugging accuracy."""
    out = ROOT / "logs" / f"gaze_calibration_{time.strftime('%Y%m%d_%H%M%S')}.json"
    out.parent.mkdir(exist_ok=True)
    vt = [valid_c.target_px(i) for i in range(len(valid_c.points))]
    data = {
        "screen": size,
        "ear_threshold_after_calibration": ear_threshold,
        "open_ear_median": median(calib_c.ears) if calib_c.ears else None,
        "calibration": [dict(d, feature=f) for d, f in zip(calib_c.debug, calib_c.features)],
        "validation": [dict(d, feature=f, predicted=calib.map(f), target_px=t)
                       for d, f, t in zip(valid_c.debug, valid_c.features, vt)],
        "error_px": error_px,
    }
    out.write_text(json.dumps(data, indent=2))
    return out


def main() -> int:
    W, H = screen_size()
    tracker = GazeTracker(int(os.getenv("GAZE_CAMERA_INDEX", "0")))
    if not tracker.open():
        print("Could not open the camera. Allow camera access for your terminal / VS Code in "
              "System Settings > Privacy & Security > Camera, then run again.")
        return 1

    cv2.namedWindow(WINDOW, cv2.WINDOW_NORMAL)
    cv2.setWindowProperty(WINDOW, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)

    phase, collector = "intro", None
    calib, error_px = GazeCalibration(), None
    fx, fy = OneEuroFilter(min_cutoff=1.0, beta=0.01), OneEuroFilter(min_cutoff=1.0, beta=0.01)
    blinks, flash_until, last_how = 0, 0, "-"
    dwell = DwellSelector()
    box_hits = [0] * 9

    try:
        while True:
            sample = tracker.read()
            if not sample or not sample.get("camera_ok"):
                print("Camera returned no frame.")
                break
            img = np.full((H, W, 3), BG, np.uint8)
            face = sample.get("face", False)

            if phase == "intro":
                text(img, "AccessShift GazeControl", (40, 80), 1.4, ACCENT, 3)
                text(img, "Sit about an arm's length from the screen, face centred in the camera.", (40, 150))
                text(img, "Press SPACE, then follow each dot with your eyes only.", (40, 195))
                text(img, "Face found" if face else "No face found - look at the camera",
                     (40, 260), 0.9, OK if face else WARN)

            elif phase in ("calibrate", "validate"):
                collector.update(sample, tracker.blink.ear_threshold * 1.1)
                if not face:
                    text(img, "Face not found - look at the camera", (40, H - 40), 0.9, WARN)
                if collector.done and phase == "calibrate":
                    tracker.blink.calibrate_open(collector.ears)
                    targets = [collector.target_px(i) for i in range(len(CALIBRATION_POINTS))]
                    calib.fit(collector.features, targets)
                    calib_collector = collector
                    phase, collector = "validate", PointCollector(VALIDATION_POINTS, (W, H))
                elif collector.done and phase == "validate":
                    targets = [collector.target_px(i) for i in range(len(VALIDATION_POINTS))]
                    error_px = calib.error_px(collector.features, targets)
                    log = save_debug(calib_collector, collector, calib, error_px, tracker.blink.ear_threshold, (W, H))
                    print(f"Accuracy +/-{error_px:.0f} px - details saved to {log}")
                    dwell = DwellSelector(adaptive_dwell_ms(error_px))
                    phase = "live"
                else:
                    collector.draw(img, "Calibrating" if phase == "calibrate" else "Checking accuracy", sample["ts_ms"])

            if phase == "live":
                cols, rows = 3, 3
                bw, bh = W // cols, H // rows
                gaze_box, progress = None, 0.0
                if face:
                    gx, gy = calib.map(sample["feature"])
                    t = sample["ts_ms"] / 1000.0
                    gx = min(max(fx.filter(gx, t), 0), W - 1)
                    gy = min(max(fy.filter(gy, t), 0), H - 1)
                    gaze_box = min(int(gy // bh), rows - 1) * cols + min(int(gx // bw), cols - 1)
                state = dwell.update(gaze_box, sample["ts_ms"])
                progress = state.progress
                if face and sample["blink"]:
                    blinks += 1
                if gaze_box is not None and (state.fired or sample["blink"]):
                    box_hits[gaze_box] += 1
                    flash_until = sample["ts_ms"] + 400
                    last_how = "dwell" if state.fired else "blink"
                    dwell.consume()
                for i in range(9):
                    x0, y0 = (i % cols) * bw, (i // cols) * bh
                    active = i == gaze_box
                    flashing = active and sample["ts_ms"] < flash_until
                    if active:
                        cv2.rectangle(img, (x0 + 6, y0 + 6), (x0 + bw - 6, y0 + bh - 6),
                                      OK if flashing else (60, 60, 70), -1)
                    cv2.rectangle(img, (x0 + 6, y0 + 6), (x0 + bw - 6, y0 + bh - 6), (90, 90, 100), 2)
                    text(img, f"Box {i + 1}   selected {box_hits[i]}", (x0 + 24, y0 + 44), 0.7)
                if face:
                    cv2.circle(img, (int(gx), int(gy)), 18, ACCENT, -1, cv2.LINE_AA)
                    cv2.circle(img, (int(gx), int(gy)), 26, (70, 70, 80), 3, cv2.LINE_AA)
                    if progress > 0:  # dwell ring fills clockwise from the top
                        cv2.ellipse(img, (int(gx), int(gy)), (26, 26), -90, 0, 360 * progress, OK, 4, cv2.LINE_AA)
                else:
                    text(img, "Face not found - look at the camera", (40, H // 2), 1.0, WARN)
                status = (f"Accuracy +/-{error_px:.0f} px   Dwell {dwell.dwell_ms} ms   "
                          f"Deliberate blinks {blinks}   Last select: {last_how}")
                text(img, status, (24, H - 24), 0.7, FG)
                text(img, "R recalibrate   Q quit", (W - 300, H - 24), 0.7, FG)

            # webcam inset, bottom-right
            if "frame" in sample:
                cam = sample["frame"]
                iw = min(320, W // 4)
                ih = int(cam.shape[0] * iw / cam.shape[1])
                inset = cv2.resize(cam, (iw, ih))
                x0, y0 = W - iw - 16, H - ih - 56
                img[y0:y0 + ih, x0:x0 + iw] = inset
                cv2.rectangle(img, (x0, y0), (x0 + iw, y0 + ih), OK if face else WARN, 2)

            cv2.imshow(WINDOW, img)
            key = cv2.waitKey(1) & 0xFF
            if key in (ord("q"), 27):
                break
            if (key == ord(" ") and phase == "intro") or key == ord("r"):
                phase, collector = "calibrate", PointCollector(CALIBRATION_POINTS, (W, H))
                calib, error_px, blinks, box_hits = GazeCalibration(), None, 0, [0] * 9
                last_how = "-"
    finally:
        tracker.close()
        cv2.destroyAllWindows()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
