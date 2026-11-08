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

from PySide6.QtCore import QRect, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QGuiApplication, QPainter, QPen
from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QPushButton, QVBoxLayout

from accessshift.modules.gaze.calibration import (
    CALIBRATION_POINTS,
    HEAD_POSES,
    DotCollector,
    GazeCalibration,
    head_calibration,
)
from accessshift.modules.gaze.controller import GazeController

VALIDATION_POINTS = [(0.3, 0.3), (0.7, 0.3), (0.3, 0.7), (0.7, 0.7)]
# Head tilt (especially UP) drops eyelid EAR and adds wobble. Stay loose so steps advance.
HEAD_MAX_SPREAD = 0.09
HEAD_SETTLE_MS = 900
HEAD_COLLECT_MS = 1800
HEAD_MAX_RETRIES = 3
HEAD_EAR_FLOOR = 0.05  # face present is enough; do not require wide-open eyes
EYES_SETTLE_MS = 700
EYES_COLLECT_MS = 1400
EYES_MAX_RETRIES = 2
# Webcam eye features jitter even when you feel still; 0.01 was rejecting good holds.
EYES_MAX_SPREAD = 0.055
EYES_INSTRUCTION = (
    "Sit an arm's length from the screen. Keep your head still and move only your eyes "
    "to the blue dot. Hold each gaze until the ring fills."
)
HEAD_INSTRUCTION = (
    "Sit centered in front of the camera. Move your head only (not your chair). "
    "Follow each arrow, then hold still until the ring fills."
)
# Where each head pose's arrow points (normalized screen), in HEAD_POSES order.
HEAD_TARGETS = {"center": (0.5, 0.5), "left": (0.1, 0.5), "right": (0.9, 0.5), "up": (0.5, 0.1), "down": (0.5, 0.9)}
HEAD_STEP_TEXT = {
    "center": "Face the screen straight ahead",
    "left": "Turn your head LEFT",
    "right": "Turn your head RIGHT",
    "up": "Tilt your chin UP",
    "down": "Tilt your chin DOWN",
}
HEAD_STEP_DETAIL = {
    "center": "Look at the middle of the screen. Shoulders square, jaw relaxed. Hold until the ring fills.",
    "left": "Rotate left as far as is comfortable. Keep your eyes open and your nose pointing left. Hold.",
    "right": "Rotate right as far as is comfortable. Keep your eyes open and your nose pointing right. Hold.",
    "up": "Lift your chin toward the ceiling a little. Do not tip your whole body back. Eyes can feel more closed; that is normal. Hold.",
    "down": "Tuck your chin toward your chest a little. Keep looking at the screen area. Hold.",
}
DEFAULT_EAR_THRESHOLD = 0.21

BG = QColor(11, 31, 58)  # navy paper field
FG = QColor(244, 247, 251)
ACCENT = QColor(47, 111, 237)  # AccessShift blue
WARN = QColor(200, 120, 120)
OK = QColor(150, 200, 240)


class GazeCalibrationDialog(QDialog):
    def __init__(
        self,
        controller: GazeController,
        screen_rect: QRect | None = None,
        result_delay_ms: int = 1500,
        parent=None,
        points=CALIBRATION_POINTS,
        validation_points=VALIDATION_POINTS,
        max_spread: float = EYES_MAX_SPREAD,
        instruction: str = EYES_INSTRUCTION,
        head: bool = False,
        settle_ms: int = EYES_SETTLE_MS,
        collect_ms: int = EYES_COLLECT_MS,
        max_retries: int = EYES_MAX_RETRIES,
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
        self._collect_ms = collect_ms
        self._max_retries = max_retries
        self._head = head  # guided head poses instead of dots
        self.instruction = instruction
        self._phase = "idle"
        self._collector: DotCollector | None = None
        self._calibration: GazeCalibration | None = None
        self._ear_threshold = HEAD_EAR_FLOOR if head else DEFAULT_EAR_THRESHOLD
        self._ts = 0
        self._face = True
        self._ear = 1.0
        self._camera_ok = True
        self._message = ""  # result text, or live restart coach
        self._listening = False

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
            kwargs.setdefault("collect_ms", HEAD_COLLECT_MS)
            kwargs.setdefault("max_retries", HEAD_MAX_RETRIES)
        else:
            kwargs.setdefault("max_spread", EYES_MAX_SPREAD)
            kwargs.setdefault("settle_ms", EYES_SETTLE_MS)
            kwargs.setdefault("collect_ms", EYES_COLLECT_MS)
            kwargs.setdefault("max_retries", EYES_MAX_RETRIES)
        return cls(controller, **kwargs)

    @staticmethod
    def choose_source(current: str = "head", parent=None) -> str | None:
        """Ask whether to calibrate head or eyes. Returns 'head', 'eyes', or None if cancelled."""
        dlg = QDialog(parent, Qt.WindowStaysOnTopHint)
        dlg.setWindowTitle("Choose pointing mode")
        dlg.setModal(True)
        dlg.setMinimumSize(520, 280)
        dlg.setStyleSheet(
            "QDialog { background: #0B1F3A; }"
            "QLabel { color: #F4F7FB; background: transparent; }"
            "QLabel#title { font-size: 28px; font-weight: 200; letter-spacing: -0.4px; }"
            "QLabel#hint { font-size: 15px; color: #B8C9DE; }"
            "QPushButton {"
            "  background: #123A6D; color: #F4F7FB; font-size: 18px; font-weight: 650;"
            "  border: 1px solid #2F6FED; border-radius: 18px; padding: 22px 18px; min-height: 88px;"
            "}"
            "QPushButton:hover { background: #1E4F8C; border-color: #5B8FF5; }"
            "QPushButton#preferred { border: 3px solid #2F6FED; background: #163A6E; }"
        )
        layout = QVBoxLayout(dlg)
        layout.setContentsMargins(28, 28, 28, 28)
        layout.setSpacing(16)
        title = QLabel("What should we calibrate?")
        title.setObjectName("title")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)
        hint = QLabel(
            "Head pointing: turn and tilt your head toward buttons.\n"
            "Eye pointing: keep your head still and look with your eyes."
        )
        hint.setObjectName("hint")
        hint.setAlignment(Qt.AlignCenter)
        hint.setWordWrap(True)
        layout.addWidget(hint)

        chosen: dict[str, str | None] = {"value": None}
        row = QHBoxLayout()
        row.setSpacing(14)

        def pick(source: str) -> None:
            chosen["value"] = source
            dlg.accept()

        head_btn = QPushButton("Head pointing")
        eyes_btn = QPushButton("Eye pointing")
        if current == "eyes":
            eyes_btn.setObjectName("preferred")
        else:
            head_btn.setObjectName("preferred")
        head_btn.clicked.connect(lambda: pick("head"))
        eyes_btn.clicked.connect(lambda: pick("eyes"))
        row.addWidget(head_btn)
        row.addWidget(eyes_btn)
        layout.addLayout(row)

        cancel = QPushButton("Cancel")
        cancel.setStyleSheet(
            "QPushButton { min-height: 48px; font-size: 16px; border-radius: 10px; }"
        )
        cancel.clicked.connect(dlg.reject)
        layout.addWidget(cancel)

        if dlg.exec() != QDialog.DialogCode.Accepted:
            return None
        return chosen["value"]

    def current_step(self) -> str:
        """Head mode: which pose is being asked for ("center", "left", ...)."""
        return HEAD_POSES[min(self._collector.index, len(HEAD_POSES) - 1)]

    def message(self) -> str:
        return self._message

    # --- lifecycle ---------------------------------------------------------------------
    def begin(self) -> None:
        """Show and start calibrating without blocking (exec() blocks; tests use this)."""
        self._start("calibrate", self._points)
        self._ctrl.paused = True
        if not self._listening:
            self._ctrl.raw_sample.connect(self._on_sample)
            self._listening = True
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
            points,
            (self._rect.width(), self._rect.height()),
            settle_ms=self._settle_ms,
            collect_ms=self._collect_ms,
            max_spread=self._max_spread,
            max_retries=self._max_retries,
        )

    def _global_targets(self) -> list[tuple[float, float]]:
        return [(x + self._rect.left(), y + self._rect.top()) for x, y in self._collector.targets_px()]

    def _on_sample(self, sample: dict) -> None:
        if self._phase not in ("calibrate", "validate"):
            return
        self._ts = sample.get("ts_ms", self._ts)
        self._face = bool(sample.get("face"))
        self._ear = float(sample.get("ear", 1.0))
        self._camera_ok = bool(sample.get("camera_ok", True))
        self._collector.update(sample, self._ear_threshold)
        if self._collector.done:
            self._advance()
        self.update()

    def _status_hint(self, c: DotCollector) -> tuple[str, QColor]:
        """Contextual coach text for the current sample / retry state."""
        if not self._camera_ok:
            return ("Camera not ready. Check the webcam cable and Camera privacy settings.", WARN)
        if not self._face:
            return ("Face not found. Sit facing the camera with light on your face.", WARN)
        if not self._head and self._ear < self._ear_threshold:
            return ("Eyes look closed. Open them and look straight at the blue dot.", WARN)
        # Restart coach stays until the next finish/cancel; live issues above still win.
        if self._message and self._phase != "result":
            return (self._message, WARN)
        if c.retries >= self._max_retries:
            return (
                "Almost done. Hold on the target a moment longer; "
                "the steadiest part of this hold will be used.",
                WARN,
            )
        if c.retries:
            if self._head:
                tip = "Hold the pose a bit longer with less wobble."
            else:
                tip = "Keep looking at the blue dot. Small natural tremor is fine."
            return (f"Hold again ({c.retries} of {self._max_retries}). {tip}", WARN)
        progress = c.progress(self._ts)
        if progress <= 0:
            if self._head:
                return ("Get into position, then hold still. The ring fills while we measure.", FG)
            return ("Find the blue dot with your eyes, then hold still.", FG)
        if progress < 1:
            return ("Hold still… measuring.", OK)
        return ("", FG)

    def _advance(self) -> None:
        c = self._collector
        if self._phase == "calibrate" and self._head:
            try:
                calibration = head_calibration(
                    dict(zip(HEAD_POSES, c.features)), (self._rect.width(), self._rect.height())
                )
            except ValueError as problem:  # barely moved: explain and start again
                detail = str(problem)
                if "left and right" in detail.lower():
                    self._message = (
                        "Left/right movement was too small. Turn farther toward each shoulder, "
                        "hold each side, then we will restart from the beginning."
                    )
                elif "up and down" in detail.lower():
                    self._message = (
                        "Up/down movement was too small. Chin farther up, then farther down, "
                        "hold each pose, then we will restart from the beginning."
                    )
                else:
                    self._message = f"{detail}. Hold each pose longer, then we will try again."
                self._start("calibrate", self._points)
                return
            calibration._coef[0] += (self._rect.left(), self._rect.top())  # screen offset
            # Only use clearly open-eye samples for blink threshold. Up-tilt ears are often low.
            open_ears = [e for e in c.ears if e >= DEFAULT_EAR_THRESHOLD]
            if open_ears:
                self._ctrl.calibrate_blink(open_ears)
            self._calibration = calibration
            # Score against the intended screen anchors for each pose (real error, not a constant).
            intended = [
                (HEAD_TARGETS[pose][0] * self._rect.width() + self._rect.left(),
                 HEAD_TARGETS[pose][1] * self._rect.height() + self._rect.top())
                for pose in HEAD_POSES
            ]
            self._finish(calibration.error_px(c.features, intended))
            return
        if self._phase == "calibrate":
            self._calibration = GazeCalibration()
            self._calibration.fit(c.features, self._global_targets())
            if c.ears:
                self._ctrl.calibrate_blink(c.ears)
                self._ear_threshold = 0.75 * median(c.ears) * 1.1
            if self._validation_points:
                self._message = ""
                self._start("validate", self._validation_points)
                return

        self._finish(self._calibration.error_px(c.features, self._global_targets()))

    def _finish(self, error_px: float) -> None:
        self._ctrl.set_calibration(self._calibration, error_px)
        self._phase = "result"
        if error_px < 40:
            quality = "Great tracking"
        elif error_px < 100:
            quality = "Good enough to start"
        else:
            quality = "Usable, but recalibrate later if pointing feels off"
        self._message = f"{quality}\nAccuracy ±{error_px:.0f} px"
        self._stop_listening()
        if self._result_delay_ms <= 0:
            self.accept()
        else:
            QTimer.singleShot(self._result_delay_ms, self.accept)

    def _draw_wrapped(self, p: QPainter, rect: QRect, text: str, align=Qt.AlignLeft | Qt.AlignTop) -> None:
        p.drawText(rect, int(align | Qt.TextWordWrap), text)

    # --- drawing -----------------------------------------------------------------------
    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), BG)
        p.setFont(QFont("Helvetica", 20))
        p.setPen(FG)

        if self._phase == "result":
            p.setFont(QFont("Helvetica", 36, QFont.Bold))
            p.setPen(OK)
            self._draw_wrapped(
                p, self.rect().adjusted(40, 0, -40, 0),
                f"Calibration done\n{self._message}",
                Qt.AlignCenter,
            )
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
        phase_tip = (
            self.instruction
            if self._phase == "calibrate"
            else "Look at each check dot the same way. This measures how close pointing lands."
        )
        p.setFont(QFont("Helvetica", 18))
        self._draw_wrapped(
            p, QRect(40, 36, self.width() - 80, 90),
            f"{title}: dot {c.index + 1} of {len(c.points)}. Esc cancels.\n{phase_tip}",
        )
        hint, color = self._status_hint(c)
        if hint:
            p.setPen(color)
            p.setFont(QFont("Helvetica", 20, QFont.Bold))
            self._draw_wrapped(p, QRect(40, 130, self.width() - 80, 80), hint)

        x, y = c.target_px()
        ring = 10 + 20 * (1.0 - c.progress(self._ts))
        p.setPen(QPen(ACCENT, 3))
        p.setBrush(Qt.NoBrush)
        p.drawEllipse(QRect(int(x - ring), int(y - ring), int(2 * ring), int(2 * ring)))
        p.setPen(Qt.NoPen)
        p.setBrush(ACCENT)
        p.drawEllipse(QRect(int(x - 8), int(y - 8), 16, 16))
        p.end()

    def _paint_head_step(self, p: QPainter, c: DotCollector) -> None:
        step = self.current_step()
        w, h = self.width(), self.height()
        p.setPen(FG)
        p.setFont(QFont("Helvetica", 18))
        self._draw_wrapped(
            p, QRect(40, 36, w - 80, 70),
            f"Head calibration: step {c.index + 1} of {len(c.points)}. Esc cancels.\n{self.instruction}",
        )
        hint, color = self._status_hint(c)
        if hint:
            p.setPen(color)
            p.setFont(QFont("Helvetica", 20, QFont.Bold))
            self._draw_wrapped(p, QRect(40, 110, w - 80, 70), hint)

        p.setPen(FG)
        p.setFont(QFont("Helvetica", 34, QFont.Bold))
        p.drawText(QRect(0, h // 2 - 200, w, 50), Qt.AlignCenter, HEAD_STEP_TEXT[step])
        p.setFont(QFont("Helvetica", 18))
        self._draw_wrapped(
            p, QRect(80, h // 2 - 140, w - 160, 70),
            HEAD_STEP_DETAIL[step],
            Qt.AlignHCenter | Qt.AlignTop,
        )

        cx, cy = w // 2, h // 2 + 20
        tx, ty = c.target_px()
        # Keep left/right level and up/down plumb (target_px y=0.5 sits above the ring centre).
        if step in ("left", "right"):
            ty = float(cy)
        elif step in ("up", "down"):
            tx = float(cx)
        p.setPen(QPen(ACCENT, 14, Qt.SolidLine, Qt.RoundCap))
        if step != "center":  # big arrow from the centre toward the side to turn to
            p.drawLine(cx, cy, int(tx), int(ty))
            dx, dy = (tx - cx), (ty - cy)
            length = max(1.0, (dx * dx + dy * dy) ** 0.5)
            ux, uy = dx / length, dy / length
            for sx, sy in ((-uy, ux), (uy, -ux)):  # arrow head
                p.drawLine(int(tx), int(ty), int(tx - 50 * ux + 30 * sx), int(ty - 50 * uy + 30 * sy))
        # progress ring at the centre: fills while holding the pose
        ring = QRect(cx - 40, cy - 40, 80, 80)
        p.setPen(QPen(QColor(90, 90, 100), 8))
        p.drawEllipse(ring)
        progress = c.progress(self._ts)
        if progress > 0:
            p.setPen(QPen(ACCENT, 8))
            p.drawArc(ring, 90 * 16, -int(360 * 16 * progress))
