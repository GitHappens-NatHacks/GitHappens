"""Live motor telemetry panel for the SteadyHand practice canvas."""
from __future__ import annotations

import time

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QPolygonF
from PySide6.QtWidgets import (
    QCheckBox, QFileDialog, QFrame, QHBoxLayout, QLabel, QMessageBox,
    QPushButton, QVBoxLayout, QWidget,
)

from accessshift.ui import theme as theme_mod

# Decision threshold used by MotorTelemetry for the ON/OFF software label.
OFF_THRESHOLD = 50.0
HISTORY_N = 90


class MetricChip(QFrame):
    """One number, one unit, one short caption."""

    def __init__(self, caption: str):
        super().__init__()
        self.setObjectName("card")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 12, 14, 12)
        lay.setSpacing(2)
        self.value = QLabel("—")
        self.value.setObjectName("cardTitle")
        self.value.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.unit = QLabel(caption)
        self.unit.setObjectName("bodyText")
        self.unit.setWordWrap(True)
        lay.addWidget(self.value)
        lay.addWidget(self.unit)

    def set_value(self, text: str) -> None:
        self.value.setText(text)


class TremorTrendChart(QWidget):
    """Session tremor-index over time with a clear OFF threshold."""

    def __init__(self, metrics):
        super().__init__()
        self.metrics = metrics
        self.setMinimumHeight(220)
        self.setAccessibleName("Tremor power index over this session")

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        left, right, top, bottom = 48, 16, 28, 36
        plot = QRectF(left, top, max(1, w - left - right), max(1, h - top - bottom))

        # Plot background
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(theme_mod.SOFT_MINT))
        painter.drawRoundedRect(QRectF(0, 0, w, h), 12, 12)
        painter.setBrush(QColor(theme_mod.PURE_WHITE))
        painter.drawRoundedRect(plot, 8, 8)

        # Grid + y labels (0, 25, 50, 75, 100)
        font = QFont(painter.font())
        font.setPointSize(10)
        painter.setFont(font)
        for tick in (0, 25, 50, 75, 100):
            y = plot.bottom() - (tick / 100.0) * plot.height()
            painter.setPen(QPen(QColor("#D5E2DE"), 1, Qt.PenStyle.DotLine))
            painter.drawLine(QPointF(plot.left(), y), QPointF(plot.right(), y))
            painter.setPen(QColor(theme_mod.MUTED_GREY_GREEN))
            painter.drawText(QRectF(0, y - 8, left - 6, 16),
                             Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, str(tick))

        # OFF threshold band (above 50)
        y50 = plot.bottom() - (OFF_THRESHOLD / 100.0) * plot.height()
        band = QRectF(plot.left(), plot.top(), plot.width(), max(0, y50 - plot.top()))
        painter.setPen(Qt.PenStyle.NoPen)
        warn = QColor("#E0684F")
        warn.setAlpha(28)
        painter.setBrush(warn)
        painter.drawRect(band)
        painter.setPen(QPen(QColor("#E0684F"), 1.5, Qt.PenStyle.DashLine))
        painter.drawLine(QPointF(plot.left(), y50), QPointF(plot.right(), y50))
        painter.setPen(QColor("#E0684F"))
        painter.drawText(QRectF(plot.left() + 6, y50 - 18, 160, 16),
                         Qt.AlignmentFlag.AlignLeft, "OFF estimate ≥ 50")

        rows = self.metrics.history[-HISTORY_N:]
        painter.setPen(QColor(theme_mod.FOREST_GREEN))
        title_font = QFont(painter.font())
        title_font.setBold(True)
        title_font.setPointSize(12)
        painter.setFont(title_font)
        painter.drawText(QRectF(plot.left(), 4, plot.width(), 22),
                         Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                         "Tremor power over this session")

        if len(rows) < 2:
            painter.setFont(font)
            painter.setPen(QColor(theme_mod.MUTED_GREY_GREEN))
            painter.drawText(plot, Qt.AlignmentFlag.AlignCenter, "Waiting for pointer motion")
            painter.end()
            return

        n = len(rows)
        xs = [plot.left() + i * plot.width() / max(1, n - 1) for i in range(n)]
        ys = [plot.bottom() - min(100.0, max(0.0, row["tremor_index"])) / 100.0 * plot.height()
              for row in rows]
        points = [QPointF(x, y) for x, y in zip(xs, ys)]

        # Area under the curve
        fill = QColor(theme_mod.DEEP_TEAL)
        fill.setAlpha(55)
        painter.setBrush(fill)
        painter.setPen(Qt.PenStyle.NoPen)
        area = QPolygonF(
            list(points)
            + [QPointF(points[-1].x(), plot.bottom()), QPointF(points[0].x(), plot.bottom())]
        )
        painter.drawPolygon(area)

        # Line
        painter.setPen(QPen(QColor(theme_mod.DEEP_TEAL), 2.5))
        for a, b in zip(points, points[1:]):
            painter.drawLine(a, b)

        # Current point
        last = points[-1]
        painter.setBrush(QColor(theme_mod.DEEP_TEAL))
        painter.setPen(QPen(QColor(theme_mod.PURE_WHITE), 2))
        painter.drawEllipse(last, 5, 5)

        # Axis captions
        painter.setFont(font)
        painter.setPen(QColor(theme_mod.MUTED_GREY_GREEN))
        painter.drawText(QRectF(plot.left(), h - 28, plot.width(), 20),
                         Qt.AlignmentFlag.AlignLeft, "Older samples")
        painter.drawText(QRectF(plot.left(), h - 28, plot.width(), 20),
                         Qt.AlignmentFlag.AlignRight, "Now")
        painter.drawText(QRectF(2, top, left - 8, plot.height()),
                         Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap, "Index")
        painter.end()


class TelemetryPanel(QWidget):
    """Clinician-readable live readouts from mouse-path spectral analysis."""

    def __init__(self, controller):
        super().__init__()
        self.metrics = controller.telemetry
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 8, 0, 0)
        layout.setSpacing(10)

        title = QLabel("Motor session")
        title.setObjectName("sectionTitle")
        layout.addWidget(title)

        chips = QHBoxLayout()
        chips.setSpacing(10)
        self.chip_hz = MetricChip("Peak frequency")
        self.chip_index = MetricChip("Tremor index")
        self.chip_state = MetricChip("ON / OFF estimate")
        chips.addWidget(self.chip_hz, 1)
        chips.addWidget(self.chip_index, 1)
        chips.addWidget(self.chip_state, 1)
        layout.addLayout(chips)

        self.chart = TremorTrendChart(self.metrics)
        layout.addWidget(self.chart)

        self.summary = QLabel()
        self.summary.setObjectName("bodyText")
        self.summary.setWordWrap(True)
        layout.addWidget(self.summary)

        guard = QCheckBox("Protect clicks from accidental drags")
        guard.setChecked(controller.hold.enabled)
        guard.setToolTip(
            "Keeps the original click point steady when a brief spasm would otherwise drag or slip."
        )
        guard.toggled.connect(lambda enabled: setattr(controller.hold, "enabled", enabled))
        layout.addWidget(guard)

        self.counts = QLabel()
        self.counts.setObjectName("bodyText")
        self.counts.setWordWrap(True)
        layout.addWidget(self.counts)

        export = QPushButton("Export session")
        export.setObjectName("secondaryButton")
        export.setMinimumHeight(42)
        export.setCursor(Qt.CursorShape.PointingHandCursor)
        export.clicked.connect(self.export)
        layout.addWidget(export)

        self.previous = (0, 0)
        self.flash_until = 0.0
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh)
        self.timer.start(150)
        self.refresh()

    def refresh(self):
        m = self.metrics
        row = m.latest
        if row:
            hz = row["dominant_hz"]
            self.chip_hz.set_value(f"{hz:.1f} Hz" if hz else "—")
            self.chip_index.set_value(f"{row['tremor_index']:.0f}")
            off = row["medication_state_estimate"] == "OFF"
            self.chip_state.set_value("OFF" if off else "ON")
            source = "from the simulated tremor" if row.get("simulated") else "from the live mouse"
            if off:
                story = (
                    f"Tremor power is elevated {source}, so SteadyHand treats this window as higher load "
                    "and leans on stronger stabilization when assist is on."
                )
            else:
                story = (
                    f"Tremor power is quieter {source}, which usually means aim is tracking closer to intention."
                )
            self.summary.setText(story)
        else:
            self.chip_hz.set_value("—")
            self.chip_index.set_value("—")
            self.chip_state.set_value("—")
            self.summary.setText("Move inside the canvas for a few seconds and the session chart will fill in.")

        counts = (m.spastic_drags_prevented, m.slip_clicks_rescued)
        if counts != self.previous:
            self.flash_until = time.monotonic() + 0.8
            self.previous = counts
        flash = " Just now." if time.monotonic() < self.flash_until else ""
        self.counts.setText(f"Drags blocked {counts[0]} · Slip-clicks held {counts[1]}.{flash}")
        self.chart.update()

    def export(self):
        path, fmt = QFileDialog.getSaveFileName(
            self,
            "Export motor session",
            "motor-session",
            "CSV (*.csv);;JSON (*.json)",
        )
        if not path:
            return
        extension = ".csv" if fmt.startswith("CSV") else ".json"
        if not path.lower().endswith(extension):
            path += extension
        try:
            self.metrics.export(path)
        except OSError as error:
            QMessageBox.warning(self, "Export failed", str(error))
            return
        QMessageBox.information(
            self,
            "Export saved",
            f"Session saved to:\n{path}\n\nThis is a trend file for the care team, not a validated clinical score.",
        )
