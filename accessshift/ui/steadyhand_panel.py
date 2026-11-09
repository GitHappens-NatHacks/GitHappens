"""SteadyHand demo: the tremor practice canvas plus its trial controls.

One widget, used in two places: inside the SteadyHand tab and inside the Demo Lab.
It drives the existing SteadyHandController / TargetManager / Trial APIs unchanged.
"""
from __future__ import annotations

import time
from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (
    QComboBox, QFileDialog, QFrame, QHBoxLayout, QMessageBox, QVBoxLayout, QWidget,
)

from accessshift.modules.steadyhand.controller import SteadyHandController
from accessshift.modules.steadyhand.metrics import Trial, save_results
from accessshift.modules.steadyhand.targets import Target, TargetManager
from accessshift.ui import theme as theme_mod
from accessshift.ui.control_center_components import PreferenceRow, button, label
from accessshift.ui.motor_telemetry import TelemetryPanel

SEQUENCE = ('doctor', 'date', 'time', 'review', 'book') * 2
LABELS = {
    'doctor': '1. Doctor',
    'date': '2. Date',
    'time': '3. Time',
    'review': '4. Review',
    'book': '5. Book',
}


class TremorPlayground(QWidget):
    """In-app tremor smoothing and target assistance evaluation canvas.

    Supports baseline, smoothing, target assistance, and combined modes with
    healthcare workflow targets, live accuracy metrics, and JSON trial export.
    """
    metrics_changed = Signal(int, int)
    trial_progress = Signal(object, object)
    trial_completed = Signal(object)

    MODES = [
        'Baseline (Raw input)',
        'SteadyHand smoothing',
        'Target assistance',
        'Smoothing + Target assistance',
    ]

    def __init__(self, controller: SteadyHandController, target_padding: float = 16.0):
        super().__init__()
        self.controller = controller
        self.setMinimumHeight(300)
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.setAccessibleName('SteadyHand accuracy practice and evaluation canvas')
        self.theme = theme_mod.theme('standard')

        self.target_manager = TargetManager(padding=target_padding)
        self._mode_index = 3
        self.use_filter = True
        self.assisted = True

        self._inside = False
        self._mouse = (150.0, 130.0)
        self._raw = self._mouse
        self._stable = self._mouse
        self._interaction = self._mouse
        self._hits = 0
        self._misses = 0
        self._simulated = True
        self.controller.simulate_tremor = True
        self._sim_start = time.perf_counter()

        self.trial: Trial | None = None
        self.results: list[Trial] = []

        self.timer = QTimer(self)
        self.timer.setInterval(16)
        self.timer.timeout.connect(self._tick)
        self.timer.start()
        self._rebuild_targets()

    def set_theme(self, t: theme_mod.Theme) -> None:
        self.theme = t
        self.update()

    def set_target_padding(self, padding: float) -> None:
        self.target_manager.padding = max(0.0, float(padding))
        self.update()

    def set_mode(self, mode_index: int) -> None:
        self._mode_index = max(0, min(len(self.MODES) - 1, mode_index))
        self.use_filter = self._mode_index in (1, 3)
        self.assisted = self._mode_index in (2, 3)
        self.controller.enabled = self.use_filter
        self.controller.reset()
        self.update()

    def start_trial(self) -> None:
        self.set_mode(self._mode_index)
        self.trial = Trial(self.MODES[self._mode_index], SEQUENCE)
        self.controller.reset()
        self._sim_start = time.perf_counter()
        self.update()
        self.trial_progress.emit(self.trial.summary(), self.trial.expected)

    def abort_trial(self) -> None:
        if self.trial and not self.trial.complete:
            self.trial = None
            self.update()

    def set_simulation(self, enabled: bool) -> None:
        self._simulated = enabled
        self._sim_start = time.perf_counter()
        self.controller.simulate_tremor = enabled
        self.update()

    def reset_scores(self) -> None:
        self._hits = 0
        self._misses = 0
        self.metrics_changed.emit(0, 0)
        self.update()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._rebuild_targets()

    def _rebuild_targets(self) -> None:
        w = max(400, self.width())
        h = max(200, self.height())
        btn_w = max(80.0, min(120.0, (w - 70) / 5.0 - 10.0))
        btn_h = max(36.0, min(48.0, h * 0.16))
        margin = 35.0
        avail_w = w - 2 * margin
        step_x = (avail_w - btn_w) / 4.0 if avail_w > btn_w else 90.0
        base_y = h * 0.46
        targets = []
        for i, key in enumerate(('doctor', 'date', 'time', 'review', 'book')):
            x = margin + i * step_x
            y = base_y + ((-1) ** i) * (btn_h * 0.42)
            targets.append(Target(key, LABELS[key], x, y, btn_w, btn_h))
        self.target_manager.set_targets(targets)

    def _tick(self) -> None:
        if not self.isVisible():
            return
        x, y = self._mouse
        now = time.perf_counter()
        if not self._inside and not self._simulated and self.controller.hold.anchor is None:
            self.controller.telemetry.reset_window()
            return
        # Tremor sim + spectral sampling live inside stabilize when simulate_tremor is on.
        self.controller.enabled = self.use_filter
        stable = self.controller.stabilize(x, y, now)
        self._raw = self.controller.last_raw
        latest = self.controller.telemetry.latest
        if self.assisted and latest and latest["medication_state_estimate"] == "OFF":
            nearby = self.target_manager.select(*stable, assisted=True)
            if nearby and not nearby.contains(*stable):
                stable = (
                    min(max(stable[0], nearby.x), nearby.x + nearby.width),
                    min(max(stable[1], nearby.y), nearby.y + nearby.height),
                )
        self._interaction = stable
        self._stable = self.controller.hold.move(stable, self._raw, now)
        self.update()

    def mouseMoveEvent(self, event) -> None:
        p = event.position()
        self._mouse = (p.x(), p.y())
        self._inside = True
        super().mouseMoveEvent(event)

    def leaveEvent(self, event) -> None:
        self._inside = False
        super().leaveEvent(event)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._inside = True
            self._mouse = event.position().toTuple()
            self._tick()
            self.controller.hold.press(self._stable, self._raw, time.perf_counter())
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        hold = self.controller.hold
        if event.button() == Qt.MouseButton.LeftButton and hold.anchor is not None:
            self._mouse = event.position().toTuple()
            self._tick()
            select = self.target_manager.select
            origin = select(*hold.anchor, assisted=self.assisted)
            slipped = origin is not None and select(*self._raw, assisted=self.assisted) != origin
            sx, sy = hold.release(self._interaction, slipped)
            event.accept()
            if hold.dragging:
                return
            target = self.target_manager.select(sx, sy, assisted=self.assisted)
            if self.trial and not self.trial.complete:
                hit = self.trial.record(target.id if target else None, sx, sy)
                if hit:
                    self._hits += 1
                else:
                    self._misses += 1
                self.metrics_changed.emit(self._hits, self._misses)
                self.trial_progress.emit(self.trial.summary(), self.trial.expected)
                if self.trial.complete:
                    self.results.append(self.trial)
                    self.trial_completed.emit(self.trial)
            else:
                if target is not None:
                    self._hits += 1
                else:
                    self._misses += 1
                self.metrics_changed.emit(self._hits, self._misses)
            return
        super().mouseReleaseEvent(event)

    def hideEvent(self, event) -> None:
        self.controller.hold.anchor = None
        self.timer.stop()
        super().hideEvent(event)

    def showEvent(self, event) -> None:
        if not self.timer.isActive():
            self.timer.start()
        super().showEvent(event)

    def paintEvent(self, event) -> None:
        t = self.theme
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(QPen(QColor(t.border), 1))
        p.setBrush(QColor(t.section))
        p.drawRoundedRect(QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5), 14, 14)
        dots = QColor(t.muted)
        dots.setAlphaF(0.25)
        p.setPen(QPen(dots, 1.4))
        for gx in range(25, self.width(), 30):
            for gy in range(25, self.height(), 30):
                p.drawPoint(gx, gy)

        expected_id = self.trial.expected if (self.trial and not self.trial.complete) else None
        sx, sy = self._stable
        candidate = self.target_manager.select(sx, sy, assisted=self.assisted) if self._inside else None
        pad = self.target_manager.padding

        for target in self.target_manager.targets:
            rect = QRectF(target.x, target.y, target.width, target.height)
            if self.assisted and pad > 0:
                p.setPen(QPen(QColor(t.primary), 1, Qt.PenStyle.DashLine))
                zone = QColor(t.mint)
                p.setBrush(zone)
                p.drawRoundedRect(rect.adjusted(-pad, -pad, pad, pad), 10, 10)
            is_expected = target.id == expected_id
            if is_expected:
                p.setPen(QPen(QColor(t.primary), 2.5))
                p.setBrush(QColor(t.primary))
            else:
                p.setPen(QPen(QColor(t.border), 1.2))
                p.setBrush(QColor(t.card))
            p.drawRoundedRect(rect, 8, 8)
            p.setPen(QColor(t.on_primary if is_expected else t.text))
            font = p.font()
            font.setBold(True)
            font.setPointSize(11)
            p.setFont(font)
            p.drawText(rect, Qt.AlignmentFlag.AlignCenter, target.label)
            if candidate and candidate.id == target.id:
                p.setPen(QPen(QColor(t.active), 3))
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.drawRoundedRect(rect.adjusted(-4, -4, 4, 4), 10, 10)

        if self._inside:
            rx, ry = self._raw
            if self._simulated or self.use_filter:
                p.setPen(QPen(QColor('#E0684F'), 2))
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.drawEllipse(QPointF(rx, ry), 9, 9)
            p.setPen(QPen(QColor(t.card), 2))
            p.setBrush(QColor(t.primary))
            p.drawEllipse(QPointF(sx, sy), 6, 6)

        p.setPen(QColor(t.text))
        font = p.font()
        font.setPointSize(11)
        font.setBold(True)
        p.setFont(font)
        status_text = f'Mode: {self.MODES[self._mode_index]}'
        if self.trial and not self.trial.complete:
            status_text += f'   ·   Target {self.trial.index + 1} of 10: {LABELS.get(self.trial.expected, "")}'
        p.drawText(18, 26, status_text)
        font.setBold(False)
        font.setPointSize(10)
        p.setFont(font)
        p.setPen(QColor(t.muted))
        p.drawText(18, self.height() - 14,
                   'Red ring: your hand with tremor     Filled dot: the steadied pointer     Blue outline: what a click selects')
        p.end()


class SteadyHandTrialPanel(QFrame):
    """Mode picker, trial buttons, canvas, live score and trial history."""

    def __init__(self, controller: SteadyHandController, target_size_pct: int = 140,
                 repo_root: Path | None = None, extra: dict | None = None):
        super().__init__()
        self.setObjectName('steadyPanel')
        self.repo_root = Path(repo_root) if repo_root else Path.cwd()
        self._extra = extra or {}
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(12)

        controls = QHBoxLayout()
        controls.setSpacing(10)
        self.mode_combo = QComboBox()
        self.mode_combo.setAccessibleName('SteadyHand test mode')
        for mode in TremorPlayground.MODES:
            self.mode_combo.addItem(mode)
        self.mode_combo.setCurrentIndex(3)
        self.mode_combo.currentIndexChanged.connect(self._on_mode_changed)
        controls.addWidget(self.mode_combo, 2)
        self.btn_start = button('Start 10-step trial', 'primaryButton')
        self.btn_start.clicked.connect(self.start_trial)
        controls.addWidget(self.btn_start)
        self.btn_abort = button('Stop trial', 'secondaryButton')
        self.btn_abort.setEnabled(False)
        self.btn_abort.clicked.connect(self.abort_trial)
        controls.addWidget(self.btn_abort)
        lay.addLayout(controls)

        self.playground = TremorPlayground(controller, target_padding=16.0 * target_size_pct / 100.0)
        lay.addWidget(self.playground)
        self.score = label('Free practice: move into the canvas and click the steps.', 'cardTitle', True)
        lay.addWidget(self.score)

        self.simulation_row = PreferenceRow(
            'Simulate 5.5 Hz Parkinsonian tremor',
            'Adds a sinusoid and noise to the raw practice cursor inside this canvas only.',
            checked=True)
        self.simulation_row.changed.connect(self.playground.set_simulation)
        lay.addWidget(self.simulation_row)
        lay.addWidget(TelemetryPanel(controller))

        history = QHBoxLayout()
        self.history = label('No completed trials yet. Try Baseline first, then Smoothing + Target assistance '
                             'to see the difference.', 'bodyText', True)
        history.addWidget(self.history, 1)
        self.btn_reset = button('Reset scores', 'secondaryButton')
        self.btn_reset.clicked.connect(self.reset_scores)
        history.addWidget(self.btn_reset, 0, Qt.AlignmentFlag.AlignTop)
        self.btn_export = button('Export results', 'secondaryButton')
        self.btn_export.clicked.connect(self.export_results)
        history.addWidget(self.btn_export, 0, Qt.AlignmentFlag.AlignTop)
        lay.addLayout(history)

        self.playground.metrics_changed.connect(self._update_score)
        self.playground.trial_progress.connect(self._on_trial_progress)
        self.playground.trial_completed.connect(self._on_trial_completed)

    # --- public -------------------------------------------------------------------------------
    def set_theme(self, t: theme_mod.Theme) -> None:
        self.playground.set_theme(t)

    def set_target_size(self, pct: int) -> None:
        self.playground.set_target_padding(16.0 * pct / 100.0)

    def set_extra(self, extra: dict) -> None:
        self._extra = dict(extra)

    @property
    def trial_running(self) -> bool:
        trial = self.playground.trial
        return bool(trial and not trial.complete)

    def start_trial(self) -> None:
        self.playground.start_trial()
        self.mode_combo.setEnabled(False)
        self.btn_start.setEnabled(False)
        self.btn_abort.setEnabled(True)

    def abort_trial(self) -> None:
        self.playground.abort_trial()
        self.mode_combo.setEnabled(True)
        self.btn_start.setEnabled(True)
        self.btn_abort.setEnabled(False)
        self.score.setText('Trial stopped. Start again whenever you are ready.')

    def reset_scores(self) -> None:
        self.playground.reset_scores()
        self.score.setText('Scores reset.')

    def export_results(self) -> None:
        if not self.playground.results:
            QMessageBox.information(self, 'Export results', 'Finish at least one trial first, then export.')
            return
        default_path = str(self.repo_root / f'steadyhand-results-{int(time.time())}.json')
        path, _ = QFileDialog.getSaveFileName(self, 'Export trial results', default_path, 'JSON Files (*.json)')
        if path:
            save_results(path, self.playground.results, extra=self._extra)
            QMessageBox.information(self, 'Export results',
                                    f'Saved {len(self.playground.results)} trials to:\n{path}')

    # --- internal ------------------------------------------------------------------------------
    def _on_mode_changed(self, index: int) -> None:
        self.playground.set_mode(index)
        self.score.setText(f'{self.playground.MODES[index]}: ready. Practise freely or start a trial.')

    def _on_trial_progress(self, summary: dict, expected: str | None) -> None:
        if expected is None:
            return
        total = summary['interactions']
        acc = f"{summary['accuracy']:.0%}" if total > 0 else 'n/a'
        self.score.setText(
            f"Click {LABELS.get(expected, expected)}   ·   Hits {summary['hits']}   ·   "
            f"Misses {summary['misses']}   ·   Accuracy {acc}   ·   {summary['seconds']:.1f} s")

    def _on_trial_completed(self, trial: Trial) -> None:
        self.mode_combo.setEnabled(True)
        self.btn_start.setEnabled(True)
        self.btn_abort.setEnabled(False)
        s = trial.summary()
        self.score.setText(f"Trial complete: {s['accuracy']:.0%} accuracy in {s['seconds']:.1f} s ({trial.mode}).")
        lines = []
        for i, t in enumerate(self.playground.results, 1):
            r = t.summary()
            lines.append(f"Trial {i}   ·   {r['mode']}   ·   {r['accuracy']:.0%} accuracy   ·   "
                         f"{r['hits']} hits, {r['misses']} misses   ·   {r['seconds']:.1f} s")
        self.history.setText('\n'.join(lines))

    def _update_score(self, hits: int, misses: int) -> None:
        if self.trial_running:
            return
        n = hits + misses
        accuracy = f'{hits / n:.0%}' if n else 'n/a'
        self.score.setText(f'Free practice   ·   Hits {hits}   ·   Misses {misses}   ·   Accuracy {accuracy}')
