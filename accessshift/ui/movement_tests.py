"""Native mouse tracing tasks for the SteadyHand board."""
import csv
import json
import math
import time
from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QPainter, QPen, QPolygonF
from PySide6.QtWidgets import (QComboBox, QFileDialog, QHBoxLayout, QLabel,
                               QPushButton, QVBoxLayout, QWidget)

from accessshift.modules.steadyhand.metrics import MotorTelemetry


class TraceCanvas(QWidget):
    def __init__(self, panel):
        super().__init__(panel)
        self.panel = panel
        self.setMouseTracking(True)
        self.setMinimumHeight(230)
        self.trace = []

    def point(self, t):
        w, h = self.width(), self.height()
        task = self.panel.task.currentIndex()
        if task == 0:
            return QPointF(w / 2, h / 2)
        if task == 3:
            radius = min(w, h) * .39 * t
            angle = 4.5 * math.pi * t
            return QPointF(w / 2 + radius * math.cos(angle), h / 2 + radius * math.sin(angle))
        wave = .25 * math.sin(4 * math.pi * t) if task == 2 else 0
        return QPointF(w * (.09 + .82 * t), h * (.5 + wave))

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), QColor("#f4f7ef"))
        p.setPen(QPen(QColor("#bdcbb5"), 9))
        p.drawPolyline(QPolygonF([self.point(i / 240) for i in range(241)]))
        p.setPen(Qt.PenStyle.NoPen)
        for t, color in ((1, "#bd713e"), (0, "#337252")):
            p.setBrush(QColor(color))
            p.drawEllipse(self.point(t), 10, 10)
        labels = [(0, "Hold here")] if self.panel.task.currentIndex() == 0 else [(0, "Start"), (1, "Finish")]
        p.setPen(QColor("#214b40"))
        for t, label in labels:
            point = self.point(t)
            left = max(0, min(self.width() - 80, point.x() - 40))
            p.drawText(QRectF(left, point.y() - 34, 80, 20), Qt.AlignmentFlag.AlignCenter, label)
        p.setPen(QPen(QColor("#214e72"), 2))
        for segment in self.trace:
            p.drawPolyline(QPolygonF(segment))

    def mouseMoveEvent(self, event):
        self.panel.record(event.position())

    def leaveEvent(self, event):
        if self.panel.phase == "recording":
            self.panel.metrics.reset_window()
            self.trace.append([])

    def resizeEvent(self, event):
        if self.panel.phase != "idle":
            self.panel.finish(False)
        super().resizeEvent(event)


class MovementTests(QWidget):
    def __init__(self):
        super().__init__()
        self.phase = "idle"
        self.rows = []
        self.trial_id = 0
        self.metrics = MotorTelemetry()
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        title = QLabel("Movement tests")
        title.setObjectName("sectionTitle")
        layout.addWidget(title)
        controls = QHBoxLayout()
        self.task = QComboBox()
        self.task.addItems(["Steady hold", "Straight line", "Wave trace", "Spiral trace"])
        self.hand = QComboBox()
        self.hand.addItems(["Right hand", "Left hand"])
        self.start = QPushButton("Start trial")
        self.start.clicked.connect(self.toggle)
        for caption, widget in (("Test", self.task), ("Hand", self.hand)):
            field = QVBoxLayout()
            label = QLabel(caption)
            label.setBuddy(widget)
            field.addWidget(label)
            widget.setAccessibleName(caption)
            widget.setMinimumHeight(42)
            field.addWidget(widget)
            controls.addLayout(field)
        self.start.setObjectName("primaryButton")
        self.start.setMinimumSize(128, 42)
        controls.addWidget(self.start, 0, Qt.AlignmentFlag.AlignBottom)
        controls.addStretch()
        layout.addLayout(controls)
        self.status = QLabel("Choose a test and hand, then start the trial.")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.canvas = TraceCanvas(self)
        layout.addWidget(self.canvas)
        self.task.currentIndexChanged.connect(self.clear_trace)
        self.export = QPushButton("Export test data (CSV / JSON)")
        self.export.setObjectName("secondaryButton")
        self.export.setMinimumHeight(42)
        self.export.setEnabled(False)
        self.export.clicked.connect(self.save)
        layout.addWidget(self.export, 0, Qt.AlignmentFlag.AlignLeft)
        self.clock = QTimer(self)
        self.clock.timeout.connect(self.tick)

    def clear_trace(self):
        self.canvas.trace = [[]]
        self.canvas.update()

    def toggle(self):
        if self.phase != "idle":
            self.finish(False)
            return
        self.clear_trace()
        self.metrics = MotorTelemetry()
        self.trial_id += 1
        self.phase = "warmup"
        self.deadline = time.monotonic() + 4
        self.start.setText("Cancel trial")
        self.task.setEnabled(False)
        self.hand.setEnabled(False)
        self.clock.start(100)
        self.tick()

    def tick(self):
        now = time.monotonic()
        if self.phase == "warmup":
            left = math.ceil(self.deadline - now)
            if left > 0:
                self.status.setText(f"Warmup · {left} seconds. Place the mouse on the green dot.")
                return
            self.phase = "ready"
            self.status.setText("Move on the green dot to begin.")
        if self.phase == "recording" and self.task.currentIndex() == 0 and now >= self.deadline:
            self.finish(True)

    def record(self, point):
        now = time.monotonic()
        if self.phase == "ready" and (point - self.canvas.point(0)).manhattanLength() <= 12:
            self.phase = "recording"
            self.deadline = now + 30
            self.status.setText("Hold steady for 30 seconds." if not self.task.currentIndex()
                                else "Trace to the orange target to finish.")
        if self.phase != "recording":
            return
        if not self.task.currentIndex() and now >= self.deadline:
            self.finish(True)
            return
        segment = self.canvas.trace[-1]
        hit = False
        if self.task.currentIndex():
            target = self.canvas.point(1)
            previous = segment[-1] if segment else point
            delta = point - previous
            offset = previous - target
            a = QPointF.dotProduct(delta, delta)
            b = QPointF.dotProduct(offset, delta)
            c = QPointF.dotProduct(offset, offset) - 100
            if a and b*b >= a*c:
                fraction = (-b - math.sqrt(b*b-a*c)) / a
                if 0 <= fraction <= 1:
                    point = previous + delta * fraction
                    hit = True
            if c <= 0:
                hit = True
        segment.append(point)
        self.metrics.sample(point.x(), point.y(), now)
        self.canvas.update()
        if hit:
            self.finish(True)

    def finish(self, save):
        self.phase = "idle"
        self.clock.stop()
        self.start.setText("Start trial")
        self.task.setEnabled(True)
        self.hand.setEnabled(True)
        if save:
            measurements = [dict(row, medication_state_estimate=None, trial_id=self.trial_id,
                                 test=self.task.currentText(), hand=self.hand.currentText())
                            for row in self.metrics.history]
            self.rows.extend(measurements)
            self.export.setEnabled(bool(self.rows))
            if measurements:
                self.status.setText(f"Trial complete · {len(measurements)} measurements ready to export.")
            else:
                self.status.setText("Trial complete. Too little continuous mouse movement to measure. "
                                    "Try again with a slow, continuous trace." if self.task.currentIndex()
                                    else "Trial complete. Too little continuous mouse movement to measure during the hold.")
        else:
            self.status.setText("Trial cancelled.")

    def hideEvent(self, event):
        if self.phase != "idle":
            self.finish(False)
        super().hideEvent(event)

    def save(self):
        name, kind = QFileDialog.getSaveFileName(self, "Export movement measurements",
                                                 "movement-tests", "CSV (*.csv);;JSON (*.json)")
        if not name:
            return
        path = Path(name)
        if not path.suffix:
            path = path.with_suffix(".json" if kind.startswith("JSON") else ".csv")
        with path.open("w", encoding="utf-8", newline="") as stream:
            if path.suffix.lower() == ".json":
                json.dump(self.rows, stream, indent=2)
            else:
                writer = csv.DictWriter(stream, fieldnames=self.rows[0])
                writer.writeheader()
                writer.writerows(self.rows)
