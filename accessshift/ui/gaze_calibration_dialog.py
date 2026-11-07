"""Full-screen gaze calibration.

Eyes: 9 dots, then a 4-dot accuracy check.
Head: guided poses with arrows (straight ahead, turn LEFT, RIGHT, tilt UP, DOWN).
Direction is taken from what the user did, so up is always up; if they barely moved,
it explains and starts again.

Uses the running GazeController's samples. While open, the controller is paused
(nothing gets clicked). On success it calls controller.set_calibration(cal, error_px).
"""

from __future__ import annotations

from statistics import median

import time

from PySide6.QtCore import QRect, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QGuiApplication, QPainter, QPen
from PySide6.QtWidgets import QDialog

from accessshift.modules.gaze.calibration import (
    CALIBRATION_POINTS,
    HEAD_POSES,
    DotCollector,
    GazeCalibration,
    head_calibration,
)
from accessshift.modules.gaze.controller import GazeController

VALIDATION_POINTS = [(0.3, 0.3), (0.7, 0.3), (0.3, 0.7), (0.7, 0.7)]
HEAD_MAX_SPREAD = 0.03  # head features are bigger than eye features, so allow more wobble
HEAD_SETTLE_MS = 900  # heads move slower than eyes
HEAD_ERROR_PX = 150  # nominal accuracy for head mode (sets a calm ~1.4 s dwell)
EYES_INSTRUCTION = "Look at the dot and keep your head still."
HEAD_INSTRUCTION = "Follow the arrows with your head and hold each pose."
# Where each head pose's arrow points (normalized screen), in HEAD_POSES order.
HEAD_TARGETS = {"center": (0.5, 0.5), "left": (0.1, 0.5), "right": (0.9, 0.5), "up": (0.5, 0.1), "down": (0.5, 0.9)}
HEAD_STEP_TEXT = {
    "center": "Face the screen straight ahead and hold still",
    "left": "Turn your head LEFT as far as is comfortable, and hold",
    "right": "Turn your head RIGHT as far as is comfortable, and hold",
    "up": "Tilt your head UP as far as is comfortable, and hold",
    "down": "Tilt your head DOWN as far as is comfortable, and hold",
}
DEFAULT_EAR_THRESHOLD = 0.21
NO_FACE = "Face not found. Look at the camera."
NO_CAMERA = "No camera picture. Check that the camera is connected and allowed for this app."
NO_CAMERA_AFTER_MS = 2500

BG = QColor(24, 24, 28)
FG = QColor(235, 235, 235)
ACCENT = QColor(255, 170, 0)
WARN = QColor(230, 90, 90)


class GazeCalibrationDialog(QDialog):
    def __init__(
        self,
        controller: GazeController,
        screen_rect: QRect | None = None,
        result_delay_ms: int = 1500,
        parent=None,
        points=CALIBRATION_POINTS,
        validation_points=VALIDATION_POINTS,
        max_spread: float = 0.01,
        instruction: str = EYES_INSTRUCTION,
        head: bool = False,
        settle_ms: int = 500,
        palette=None,
    ):
        super().__init__(parent, Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setWindowTitle("Gaze calibration")
        self._ctrl = controller
        self._rect = screen_rect or QGuiApplication.primaryScreen().geometry()
        self._result_delay_ms = result_delay_ms
        self._points = points
        self._validation_points = validation_points  # None: skip the accuracy pass
        self._max_spread = max_spread
        self._settle_ms = settle_ms
        self._head = head  # guided head poses instead of dots
        self._bg, self._fg, self._accent = BG, FG, ACCENT
        if palette is not None:  # match the app's colour setting
            self._bg, self._fg, self._accent = (
                QColor(palette.background), QColor(palette.foreground), QColor(palette.accent)
            )
        self.instruction = instruction
        self._phase = "idle"
        self._collector: DotCollector | None = None
        self._calibration: GazeCalibration | None = None
        self._ear_threshold = DEFAULT_EAR_THRESHOLD * 1.1
        self._ts = 0
        self._face = True
        self._message = ""
        self._problem = ""  # big warning in the middle of the screen
        self._listening = False
        self._started_ms = 0
        self._last_sample_ms: int | None = None
        self._camera_timer = QTimer(self)
        self._camera_timer.setInterval(500)
        self._camera_timer.timeout.connect(lambda: self.check_camera(_now_ms()))

    @classmethod
    def for_controller(cls, controller: GazeController, **kwargs) -> "GazeCalibrationDialog":
        """Calibration that fits the controller's pointer source (head or eyes)."""
        if controller.source == "head":
            kwargs.setdefault("points", [HEAD_TARGETS[p] for p in HEAD_POSES])
            kwargs.setdefault("validation_points", None)
            kwargs.setdefault("max_spread", HEAD_MAX_SPREAD)
            kwargs.setdefault("instruction", HEAD_INSTRUCTION)
            kwargs.setdefault("head", True)
            kwargs.setdefault("settle_ms", HEAD_SETTLE_MS)
        return cls(controller, **kwargs)

    def current_step(self) -> str:
        """Head mode: which pose is being asked for ("center", "left", ...)."""
        return HEAD_POSES[min(self._collector.index, len(HEAD_POSES) - 1)]

    def message(self) -> str:
        return self._message

    def problem(self) -> str:
        return self._problem

    def started_ms(self) -> int:
        return self._started_ms

    def check_camera(self, now_ms: int) -> None:
        """Warn if the camera has sent nothing for a while (not connected, or not allowed)."""
        last = self._last_sample_ms if self._last_sample_ms is not None else self._started_ms
        if now_ms - last >= NO_CAMERA_AFTER_MS and self._problem != NO_CAMERA:
            self._problem = NO_CAMERA
            self.update()

    # --- lifecycle ---------------------------------------------------------------------
    def begin(self) -> None:
        """Show and start calibrating without blocking (exec() blocks; tests use this)."""
        self._start("calibrate", self._points)
        self._ctrl.paused = True
        if not self._listening:
            self._ctrl.raw_sample.connect(self._on_sample)
            self._listening = True
        self._started_ms = _now_ms()
        self._last_sample_ms = None
        self._camera_timer.start()
        self.setGeometry(self._rect)
        self.show()
        self.raise_()
        self.activateWindow()

    def run(self) -> bool:
        """Blocking: returns True if calibration finished, False if cancelled."""
        self.begin()
        return self.exec() == QDialog.DialogCode.Accepted

    def current_points(self) -> list[tuple[float, float]]:
        return self._collector.points

    def current_target_norm(self) -> tuple[float, float]:
        return self._collector.points[self._collector.index]

    def _stop_listening(self) -> None:
        self._camera_timer.stop()
        self._ctrl.paused = False
        if self._listening:
            self._ctrl.raw_sample.disconnect(self._on_sample)
            self._listening = False

    def reject(self) -> None:  # Esc or cancel
        self._stop_listening()
        super().reject()

    def accept(self) -> None:
        self._stop_listening()
        super().accept()

    # --- calibration flow --------------------------------------------------------------
    def _start(self, phase: str, points) -> None:
        self._phase = phase
        self._collector = DotCollector(
            points, (self._rect.width(), self._rect.height()),
            settle_ms=self._settle_ms, max_spread=self._max_spread,
        )

    def _global_targets(self) -> list[tuple[float, float]]:
        return [(x + self._rect.left(), y + self._rect.top()) for x, y in self._collector.targets_px()]

    def _on_sample(self, sample: dict) -> None:
        if self._phase not in ("calibrate", "validate"):
            return
        self._ts = sample.get("ts_ms", self._ts)
        self._last_sample_ms = _now_ms()
        self._face = bool(sample.get("face"))
        self._problem = "" if self._face else NO_FACE
        # Head pointing works with narrowed eyes (tilting up/down), so only eyes mode checks openness.
        self._collector.update(sample, 0.0 if self._head else self._ear_threshold)
        if self._collector.done:
            self._advance()
        self.update()

    def _advance(self) -> None:
        c = self._collector
        if self._phase == "calibrate" and self._head:
            try:
                calibration = head_calibration(
                    dict(zip(HEAD_POSES, c.features)), (self._rect.width(), self._rect.height())
                )
            except ValueError as problem:  # barely moved: explain and start again
                self._message = f"{problem}, then hold. Let's try again."
                self._start("calibrate", self._points)
                return
            calibration._coef[0] += (self._rect.left(), self._rect.top())  # screen offset
            pose_ears = [median(e) for e in c.dot_ears if e]
            if pose_ears:
                # "Closed" is measured against the narrowest held pose (usually tilting down),
                # so looking down is never mistaken for closed eyes.
                self._ctrl.calibrate_blink([min(pose_ears)])
            self._calibration = calibration
            self._finish(HEAD_ERROR_PX)
            return
        if self._phase == "calibrate":
            self._calibration = GazeCalibration()
            self._calibration.fit(c.features, self._global_targets())
            if c.ears:
                self._ctrl.calibrate_blink(c.ears)
                self._ear_threshold = 0.75 * median(c.ears) * 1.1
            if self._validation_points:
                self._start("validate", self._validation_points)
                return

        self._finish(self._calibration.error_px(c.features, self._global_targets()))

    def _finish(self, error_px: float) -> None:
        self._ctrl.set_calibration(self._calibration, error_px)
        self._phase = "result"
        self._message = f"Accuracy ±{error_px:.0f} px"
        self._stop_listening()
        if self._result_delay_ms <= 0:
            self.accept()
        else:
            QTimer.singleShot(self._result_delay_ms, self.accept)

    # --- drawing -----------------------------------------------------------------------
    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), self._bg)
        if self._problem:  # big, central, never under the Dock
            banner = QRect(self.width() // 2 - 520, self.height() // 2 + 90, 1040, 76)
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(200, 40, 40))
            p.drawRoundedRect(banner, 16, 16)
            p.setPen(QColor(255, 255, 255))
            p.setFont(QFont("Helvetica", 22, QFont.Bold))
            p.drawText(banner, Qt.AlignCenter | Qt.TextWordWrap, self._problem)
            p.setBrush(Qt.NoBrush)
        p.setFont(QFont("Helvetica", 20))
        p.setPen(self._fg)

        if self._phase == "result":
            p.setFont(QFont("Helvetica", 36, QFont.Bold))
            p.drawText(self.rect(), Qt.AlignCenter, f"Calibration done\n{self._message}")
            p.end()
            return

        if self._collector is None or self._collector.done:
            p.end()
            return

        c = self._collector
        if self._head:
            self._paint_head_step(p, c)
            p.end()
            return
        title = "Calibrating" if self._phase == "calibrate" else "Checking accuracy"
        p.drawText(40, 60, f"{title}: dot {c.index + 1} of {len(c.points)}. {self.instruction} Esc cancels.")
        if c.retries:
            p.setPen(WARN)
            p.drawText(40, 100, "Hold your eyes still on the dot. Trying again.")

        x, y = c.target_px()
        ring = 10 + 20 * (1.0 - c.progress(self._ts))
        p.setPen(QPen(self._accent, 3))
        p.setBrush(Qt.NoBrush)
        p.drawEllipse(QRect(int(x - ring), int(y - ring), int(2 * ring), int(2 * ring)))
        p.setPen(Qt.NoPen)
        p.setBrush(self._accent)
        p.drawEllipse(QRect(int(x - 8), int(y - 8), 16, 16))
        p.end()

    def _paint_head_step(self, p: QPainter, c: DotCollector) -> None:
        step = self.current_step()
        w, h = self.width(), self.height()
        p.setPen(self._fg)
        p.setFont(QFont("Helvetica", 20))
        p.drawText(40, 60, f"Head calibration: step {c.index + 1} of {len(c.points)}. Esc cancels.")
        if self._message:
            p.setPen(WARN)
            p.drawText(40, 100, self._message)

        p.setPen(self._fg)
        p.setFont(QFont("Helvetica", 34, QFont.Bold))
        p.drawText(QRect(0, h // 2 - 160, w, 60), Qt.AlignCenter, HEAD_STEP_TEXT[step])

        cx, cy = w // 2, h // 2
        tx, ty = c.target_px()
        p.setPen(QPen(self._accent, 14, Qt.SolidLine, Qt.RoundCap))
        if step != "center":  # big arrow from the centre toward the side to turn to
            p.drawLine(cx, cy, int(tx), int(ty))
            dx, dy = (tx - cx), (ty - cy)
            length = max(1.0, (dx * dx + dy * dy) ** 0.5)
            ux, uy = dx / length, dy / length
            for sx, sy in ((-uy, ux), (uy, -ux)):  # arrow head
                p.drawLine(int(tx), int(ty), int(tx - 50 * ux + 30 * sx), int(ty - 50 * uy + 30 * sy))
        # progress ring at the centre: fills while holding the pose
        p.setBrush(Qt.NoBrush)
        ring = QRect(cx - 40, cy - 40, 80, 80)
        p.setPen(QPen(QColor(90, 90, 100), 8))
        p.drawEllipse(ring)
        progress = c.progress(self._ts)
        if progress > 0:
            p.setPen(QPen(self._accent, 8))
            p.drawArc(ring, 90 * 16, -int(360 * 16 * progress))


def _now_ms() -> int:
    return int(time.monotonic() * 1000)
