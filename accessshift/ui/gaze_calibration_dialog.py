"""Full-screen 9-dot gaze calibration, then a 4-dot accuracy check.

Uses the running GazeController's samples. While open, the controller is paused
(nothing gets clicked). On success it calls controller.set_calibration(cal, error_px).
"""

from __future__ import annotations

from statistics import median

from PySide6.QtCore import QRect, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QGuiApplication, QPainter, QPen
from PySide6.QtWidgets import QDialog

from accessshift.modules.gaze.calibration import CALIBRATION_POINTS, DotCollector, GazeCalibration
from accessshift.modules.gaze.controller import GazeController

VALIDATION_POINTS = [(0.3, 0.3), (0.7, 0.3), (0.3, 0.7), (0.7, 0.7)]
DEFAULT_EAR_THRESHOLD = 0.21

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
    ):
        super().__init__(parent, Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setWindowTitle("Gaze calibration")
        self._ctrl = controller
        self._rect = screen_rect or QGuiApplication.primaryScreen().geometry()
        self._result_delay_ms = result_delay_ms
        self._phase = "idle"
        self._collector: DotCollector | None = None
        self._calibration: GazeCalibration | None = None
        self._ear_threshold = DEFAULT_EAR_THRESHOLD * 1.1
        self._ts = 0
        self._face = True
        self._message = ""
        self._listening = False

    # --- lifecycle ---------------------------------------------------------------------
    def begin(self) -> None:
        """Show and start calibrating without blocking (exec() blocks; tests use this)."""
        self._start("calibrate", CALIBRATION_POINTS)
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
        self._collector = DotCollector(points, (self._rect.width(), self._rect.height()))

    def _global_targets(self) -> list[tuple[float, float]]:
        return [(x + self._rect.left(), y + self._rect.top()) for x, y in self._collector.targets_px()]

    def _on_sample(self, sample: dict) -> None:
        if self._phase not in ("calibrate", "validate"):
            return
        self._ts = sample.get("ts_ms", self._ts)
        self._face = bool(sample.get("face"))
        self._collector.update(sample, self._ear_threshold)
        if self._collector.done:
            self._advance()
        self.update()

    def _advance(self) -> None:
        c = self._collector
        if self._phase == "calibrate":
            self._calibration = GazeCalibration()
            self._calibration.fit(c.features, self._global_targets())
            if c.ears:
                self._ctrl.calibrate_blink(c.ears)
                self._ear_threshold = 0.75 * median(c.ears) * 1.1
            self._start("validate", VALIDATION_POINTS)
            return

        error_px = self._calibration.error_px(c.features, self._global_targets())
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
        p.fillRect(self.rect(), BG)
        p.setFont(QFont("Helvetica", 20))
        p.setPen(FG)

        if self._phase == "result":
            p.setFont(QFont("Helvetica", 36, QFont.Bold))
            p.drawText(self.rect(), Qt.AlignCenter, f"Calibration done\n{self._message}")
            p.end()
            return

        if self._collector is None or self._collector.done:
            p.end()
            return

        c = self._collector
        title = "Calibrating" if self._phase == "calibrate" else "Checking accuracy"
        p.drawText(40, 60, f"{title}: dot {c.index + 1} of {len(c.points)}. "
                           "Look at the dot and keep your head still. Esc cancels.")
        if c.retries:
            p.setPen(WARN)
            p.drawText(40, 100, "Hold your eyes still on the dot. Trying again.")
        if not self._face:
            p.setPen(WARN)
            p.drawText(40, self.height() - 40, "Face not found. Look at the camera.")

        x, y = c.target_px()
        ring = 10 + 20 * (1.0 - c.progress(self._ts))
        p.setPen(QPen(ACCENT, 3))
        p.setBrush(Qt.NoBrush)
        p.drawEllipse(QRect(int(x - ring), int(y - ring), int(2 * ring), int(2 * ring)))
        p.setPen(Qt.NoPen)
        p.setBrush(ACCENT)
        p.drawEllipse(QRect(int(x - 8), int(y - 8), 16, 16))
        p.end()
