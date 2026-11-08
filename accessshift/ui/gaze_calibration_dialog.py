"""Full-screen gaze calibration.

Eyes: 9 dots, then a 4-dot accuracy check.
Head: guided poses with arrows (straight ahead, turn LEFT, RIGHT, tilt UP, DOWN).
Direction is taken from what the user did, so up is always up; if they barely moved,
it explains and starts again.

Uses the running GazeController's samples. While open, the controller is paused
(nothing gets clicked). On success it calls controller.set_calibration(cal, error_px).
"""

from __future__ import annotations

import time
from statistics import median

from PySide6.QtCore import QRect, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QGuiApplication, QPainter, QPen
from PySide6.QtWidgets import QDialog, QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout

from accessshift.modules.gaze.calibration import (
    CALIBRATION_POINTS,
    HEAD_POSES,
    DotCollector,
    GazeCalibration,
    head_calibration,
)
from accessshift.modules.gaze.controller import GazeController

VALIDATION_POINTS = [(0.3, 0.3), (0.7, 0.3), (0.3, 0.7), (0.7, 0.7)]
# Head tilt (especially up) adds wobble. Stay loose so steps advance.
HEAD_MAX_SPREAD = 0.09
HEAD_SETTLE_MS = 900  # heads move slower than eyes
HEAD_COLLECT_MS = 1800
HEAD_MAX_RETRIES = 3
EYES_SETTLE_MS = 700
EYES_COLLECT_MS = 1400
EYES_MAX_RETRIES = 2
# Webcam eye features jitter even when you feel still; 0.01 rejected good holds.
EYES_MAX_SPREAD = 0.055
EYES_INSTRUCTION = (
    "Sit an arm's length from the screen. Keep your head still and move only your eyes "
    "to the dot. Hold each gaze until the ring fills."
)
HEAD_INSTRUCTION = (
    "Sit centred in front of the camera. Move your head only, not your chair. "
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
# Small turns are enough, and they keep the face visible to the camera.
HEAD_STEP_DETAIL = {
    "center": "Look at the middle of the screen. Shoulders square, jaw relaxed. Hold until the ring fills.",
    "left": "Turn a little to the left, nose pointing left, eyes open. Hold.",
    "right": "Turn a little to the right, nose pointing right, eyes open. Hold.",
    "up": "Lift your chin a little. Your eyes may feel more closed; that is normal. Hold.",
    "down": "Tuck your chin a little, still looking toward the screen. Hold.",
}
DEFAULT_EAR_THRESHOLD = 0.21
NO_FACE = "Face not found. Look at the camera."
TURN_BACK = "Turn back a little so the camera can still see your face."
FACE_LOST_AFTER_MS = 1000  # brief losses are normal when the head is turned
NO_CAMERA = "No camera picture. Check that the camera is connected and allowed for this app."
NO_CAMERA_AFTER_MS = 2500

BG = QColor(24, 24, 28)
FG = QColor(235, 235, 235)
ACCENT = QColor(255, 170, 0)
WARN = QColor(200, 40, 40)
OK = QColor(22, 128, 80)


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
        palette=None,
    ):
        super().__init__(parent, Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setWindowTitle("Calibration")
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
        self._ear = 1.0
        self._message = ""  # result text, or why the head steps restarted
        self._problem = ""  # big warning in the middle of the screen
        self._listening = False
        self._started_ms = 0
        self._last_sample_ms: int | None = None
        self._face_lost_since: int | None = None
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
            kwargs.setdefault("collect_ms", HEAD_COLLECT_MS)
            kwargs.setdefault("max_retries", HEAD_MAX_RETRIES)
        return cls(controller, **kwargs)

    @staticmethod
    def choose_source(current: str = "head", parent=None, palette=None) -> str | None:
        """Ask whether to calibrate head or eye pointing. 'head', 'eyes', or None if cancelled.

        Full screen, so the booking options are hidden behind it, with a card in the app's
        accent colour that stands out from the page. Its buttons can be chosen by gaze too.
        """
        bg, panel, fg, accent, accent_text = "#F5F7FC", "#FFFFFF", "#1D2941", "#6347E9", "#FFFFFF"
        if palette is not None:
            bg, panel, fg, accent, accent_text = (
                palette.background, palette.panel, palette.foreground, palette.accent, palette.accent_text
            )
        dlg = QDialog(parent, Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        dlg.setWindowTitle("Choose pointing mode")
        dlg.setModal(True)
        dlg.setGeometry(QGuiApplication.primaryScreen().geometry())
        dlg.setStyleSheet(
            f"QDialog {{ background: {bg}; }}"
            f"QFrame#chooserCard {{ background: {accent}; border-radius: 24px; }}"
            f"QLabel {{ color: {accent_text}; background: transparent; }}"
            "QLabel#title { font-size: 30px; font-weight: 800; }"
            "QLabel#hint { font-size: 17px; }"
            "QPushButton {"
            f"  background: {panel}; color: {fg}; font-size: 22px; font-weight: 800;"
            f"  border: 3px solid {panel}; border-radius: 16px; padding: 22px 18px; min-height: 110px;"
            "}"
            f"QPushButton#preferred {{ border: 6px solid {fg}; }}"  # the current mode stands out
            "QPushButton#cancel { min-height: 56px; font-size: 18px; }"
        )
        outer = QVBoxLayout(dlg)
        outer.addStretch(1)
        card = QFrame()
        card.setObjectName("chooserCard")
        card.setMaximumWidth(760)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(36, 36, 36, 36)
        layout.setSpacing(18)
        title = QLabel("How do you want to point?")
        title.setObjectName("title")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)
        hint = QLabel(
            "Head pointing: turn and tilt your head toward an option.\n"
            "Eye pointing: keep your head still and look with your eyes."
        )
        hint.setObjectName("hint")
        hint.setAlignment(Qt.AlignCenter)
        hint.setWordWrap(True)
        layout.addWidget(hint)

        chosen: dict[str, str | None] = {"value": None}
        row = QHBoxLayout()
        row.setSpacing(16)

        def pick(source: str) -> None:
            chosen["value"] = source
            dlg.accept()

        head_btn = QPushButton("Head pointing")
        eyes_btn = QPushButton("Eye pointing")
        (eyes_btn if current == "eyes" else head_btn).setObjectName("preferred")
        head_btn.clicked.connect(lambda: pick("head"))
        eyes_btn.clicked.connect(lambda: pick("eyes"))
        row.addWidget(head_btn)
        row.addWidget(eyes_btn)
        layout.addLayout(row)

        cancel = QPushButton("Cancel")
        cancel.setObjectName("cancel")
        cancel.clicked.connect(dlg.reject)
        layout.addWidget(cancel)

        centre = QHBoxLayout()
        centre.addStretch(1)
        centre.addWidget(card, 3)
        centre.addStretch(1)
        outer.addLayout(centre)
        outer.addStretch(1)

        if dlg.exec() != QDialog.DialogCode.Accepted:
            return None
        return chosen["value"]

    def current_step(self) -> str:
        """Head mode: which pose is being asked for ("center", "left", ...)."""
        return HEAD_POSES[min(self._collector.index, len(HEAD_POSES) - 1)]

    def message(self) -> str:
        return self._message

    def problem(self) -> str:
        return self._problem

    def current_instruction(self) -> str:
        if not self._head:
            return self.instruction
        step = self.current_step()
        return f"{HEAD_STEP_TEXT[step]}. {HEAD_STEP_DETAIL[step]}"

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
        self._last_sample_ms = _now_ms()
        self._face = bool(sample.get("face"))
        self._ear = float(sample.get("ear", 1.0))
        if self._face:
            self._face_lost_since = None
            self._problem = ""
        else:
            if self._face_lost_since is None:
                self._face_lost_since = self._ts
            if self._ts - self._face_lost_since >= FACE_LOST_AFTER_MS:
                turned = self._head and self.current_step() != "center"
                self._problem = TURN_BACK if turned else NO_FACE
        # Head pointing works with narrowed eyes (tilting up/down), so only eyes mode checks openness.
        self._collector.update(sample, 0.0 if self._head else self._ear_threshold)
        if self._collector.done:
            self._advance()
        self.update()

    def _coach(self, c: DotCollector) -> tuple[str, QColor]:
        """Short guidance for the current moment. Face and camera problems use the big banner."""
        if self._problem:
            return ("", self._fg)
        if not self._head and self._face and self._ear < self._ear_threshold:
            return ("Eyes look closed. Open them and look at the dot.", WARN)
        if self._message and self._phase != "result":
            return (self._message, WARN)  # why the head steps restarted
        if c.retries >= self._max_retries:
            return ("Almost done. Hold a moment longer; the steadiest part will be used.", WARN)
        if c.retries:
            tip = "Hold the pose a bit longer with less wobble." if self._head else "Keep looking at the dot."
            return (f"Hold again ({c.retries} of {self._max_retries}). {tip}", WARN)
        progress = c.progress(self._ts)
        if progress <= 0:
            if self._head:
                return ("Get into position, then hold still. The ring fills while we measure.", self._fg)
            return ("Find the dot with your eyes, then hold still.", self._fg)
        if progress < 1:
            return ("Hold still… measuring.", OK)
        return ("", self._fg)

    def _advance(self) -> None:
        c = self._collector
        if self._phase == "calibrate" and self._head:
            try:
                calibration = head_calibration(
                    dict(zip(HEAD_POSES, c.features)), (self._rect.width(), self._rect.height())
                )
            except ValueError as problem:  # barely moved: explain and start again
                if "left and right" in str(problem).lower():
                    self._message = (
                        "Left and right were too small. Turn a bit farther to each side and hold. "
                        "Starting again from the beginning."
                    )
                else:
                    self._message = (
                        "Up and down were too small. Tilt your chin a bit farther up, then down, and hold. "
                        "Starting again from the beginning."
                    )
                self._start("calibrate", self._points)
                return
            calibration._coef[0] += (self._rect.left(), self._rect.top())  # screen offset
            pose_ears = [median(e) for e in c.dot_ears if e]
            if pose_ears:
                # "Closed" is measured against the narrowest held pose (usually tilting down),
                # so looking down is never mistaken for closed eyes.
                self._ctrl.calibrate_blink([min(pose_ears)])
            self._calibration = calibration
            # Score against where each pose should point (a real error, not a constant).
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
            quality = "Usable. Recalibrate later if pointing feels off"
        self._message = f"{quality}\nAccuracy ±{error_px:.0f} px"
        self._stop_listening()
        if self._result_delay_ms <= 0:
            self.accept()
        else:
            QTimer.singleShot(self._result_delay_ms, self.accept)

    # --- drawing -----------------------------------------------------------------------
    @staticmethod
    def _wrapped(p: QPainter, rect: QRect, text: str, align=Qt.AlignLeft | Qt.AlignTop) -> None:
        p.drawText(rect, int(align | Qt.TextWordWrap), text)

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), self._bg)
        if self._problem:  # big, central, never under the Dock
            banner = QRect(self.width() // 2 - 520, self.height() // 2 + 110, 1040, 76)
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
            p.setPen(OK)
            self._wrapped(p, self.rect().adjusted(40, 0, -40, 0), f"Calibration done\n{self._message}", Qt.AlignCenter)
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
        tip = (
            self.instruction if self._phase == "calibrate"
            else "Look at each check dot the same way. This measures how close pointing lands."
        )
        p.setFont(QFont("Helvetica", 18))
        self._wrapped(p, QRect(40, 36, self.width() - 80, 90),
                      f"{title}: dot {c.index + 1} of {len(c.points)}. Esc cancels.\n{tip}")
        hint, color = self._coach(c)
        if hint:
            p.setPen(color)
            p.setFont(QFont("Helvetica", 20, QFont.Bold))
            self._wrapped(p, QRect(40, 130, self.width() - 80, 80), hint)

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
        p.setFont(QFont("Helvetica", 18))
        self._wrapped(p, QRect(40, 36, w - 80, 70),
                      f"Head calibration: step {c.index + 1} of {len(c.points)}. Esc cancels.\n{self.instruction}")
        hint, color = self._coach(c)
        if hint:
            p.setPen(color)
            p.setFont(QFont("Helvetica", 20, QFont.Bold))
            self._wrapped(p, QRect(40, 110, w - 80, 70), hint)

        p.setPen(self._fg)
        p.setFont(QFont("Helvetica", 34, QFont.Bold))
        p.drawText(QRect(0, h // 2 - 200, w, 50), Qt.AlignCenter, HEAD_STEP_TEXT[step])
        p.setFont(QFont("Helvetica", 18))
        self._wrapped(p, QRect(80, h // 2 - 140, w - 160, 70), HEAD_STEP_DETAIL[step], Qt.AlignHCenter | Qt.AlignTop)

        cx, cy = w // 2, h // 2 + 20
        tx, ty = c.target_px()
        # Keep left/right arrows level and up/down arrows plumb with the ring.
        if step in ("left", "right"):
            ty = float(cy)
        elif step in ("up", "down"):
            tx = float(cx)
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
        p.setPen(QPen(QColor(150, 150, 160), 8))
        p.drawEllipse(ring)
        progress = c.progress(self._ts)
        if progress > 0:
            p.setPen(QPen(self._accent, 8))
            p.drawArc(ring, 90 * 16, -int(360 * 16 * progress))


def _now_ms() -> int:
    return int(time.monotonic() * 1000)
