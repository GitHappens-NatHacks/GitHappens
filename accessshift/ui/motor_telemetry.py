"""Live telemetry for the SteadyHand practice canvas."""
import time

from PySide6.QtCore import QPointF, QTimer
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (QCheckBox, QFileDialog, QLabel, QMessageBox,
                               QProgressBar, QPushButton, QVBoxLayout, QWidget)


class Trend(QWidget):
    def __init__(self, metrics):
        super().__init__()
        self.metrics = metrics
        self.setFixedHeight(38)
        self.setAccessibleName("Recent tremor severity trend")

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setPen(QPen(QColor("#674BE8"), 2))
        rows = self.metrics.history[-60:]
        points = [QPointF(i * self.width() / 59, 36 - row["tremor_index"] * .34)
                  for i, row in enumerate(rows)]
        for a, b in zip(points, points[1:]):
            painter.drawLine(a, b)


class TelemetryPanel(QWidget):
    def __init__(self, controller):
        super().__init__()
        self.metrics = controller.telemetry
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Clinical Motor Telemetry & Protection"))
        self.status = QLabel()
        layout.addWidget(self.status)
        self.power = QProgressBar()
        self.power.setFormat("4–7 Hz power index   %v / 100")
        layout.addWidget(self.power)
        self.trend = Trend(self.metrics)
        layout.addWidget(self.trend)
        guard = QCheckBox("Spastic Drag & Slip Guard")
        guard.setChecked(controller.hold.enabled)
        guard.toggled.connect(lambda enabled: setattr(controller.hold, "enabled", enabled))
        layout.addWidget(guard)
        self.counts = QLabel()
        layout.addWidget(self.counts)
        export = QPushButton("Export Neurologist UPDRS Report (CSV/JSON)")
        export.clicked.connect(self.export)
        layout.addWidget(export)
        layout.addWidget(QLabel("Experimental mouse telemetry. Medication labels are estimates. No UPDRS score is calculated."))
        self.previous = (0, 0)
        self.flash_until = 0
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh)
        self.timer.start(150)
        self.refresh()

    def refresh(self):
        m = self.metrics
        row = m.latest
        status = "Collecting raw samples…"
        if row:
            hz = row["dominant_hz"]
            frequency = f"{hz:.1f} Hz" if hz else "No band peak"
            state = ("OFF-STATE DETECTED [HIGH STABILIZATION]" if row["medication_state_estimate"] == "OFF"
                     else "MEDICATION ON-STATE [STABLE]")
            status = f"{frequency}   ·   {state}"
        self.status.setText(status)
        self.power.setValue(round(row["tremor_index"]) if row else 0)
        counts = (m.spastic_drags_prevented, m.slip_clicks_rescued)
        if counts != self.previous:
            self.flash_until = time.monotonic() + .8
            self.previous = counts
        flash = "   ·   Intercepted" if time.monotonic() < self.flash_until else ""
        self.counts.setText(f"Accidental Drags Blocked   {counts[0]}     Misclicks Rescued   {counts[1]}{flash}")
        self.trend.update()

    def export(self):
        path, fmt = QFileDialog.getSaveFileName(self, "Export motor telemetry", "motor-session",
                                                "CSV (*.csv);;JSON (*.json)")
        if path:
            extension = ".csv" if fmt.startswith("CSV") else ".json"
            if not path.lower().endswith(extension):
                path += extension
            try:
                self.metrics.export(path)
            except OSError as error:
                QMessageBox.warning(self, "Export failed", str(error))
