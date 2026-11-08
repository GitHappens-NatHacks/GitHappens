"""Run: python -m steadyhand_demo.demo [--yee]

--yee imports the team's existing controller; run from the repository root.
No system cursor injection is performed.
"""
import argparse
import sys
import time
from PySide6.QtCore import Qt, QRectF, QPointF, QTimer
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QComboBox, QFileDialog, QMessageBox)
from .targets import Target, TargetManager
from .metrics import Trial, save_results

SEQUENCE = ('doctor', 'date', 'time', 'review', 'book') * 2
LABELS = ('Doctor', 'Date', 'Time', 'Review', 'Book')


class Canvas(QWidget):
    def __init__(self, window):
        super().__init__()
        self.window = window
        self.setFixedSize(760, 350)
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.manager = TargetManager([
            Target(id_, label, 55+i*140, 145+(i % 2)*65, 70, 34)
            for i, (id_, label) in enumerate(zip(SEQUENCE[:5], LABELS))])
        self.position = None
        self.raw = None

    def sample(self, event):
        p = event.position()
        self.raw = (p.x(), p.y())
        self.position = self.raw
        if self.window.use_filter:
            self.position = self.window.controller.stabilize(*self.raw, time.perf_counter())
        self.update()

    def mouseMoveEvent(self, event):
        self.sample(event)

    def leaveEvent(self, event):
        self.position = None
        self.update()

    def mousePressEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            return
        self.sample(event)
        trial = self.window.trial
        if trial is None or trial.complete:
            return
        target = self.manager.select(*self.position, assisted=self.window.assisted)
        hit = trial.record(target.id if target else None, *self.position)
        self.window.feedback.setText('Hit — next target' if hit else 'Miss — try the highlighted target again')
        if trial.complete:
            self.window.finish()
        self.window.refresh()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), QColor('#101c30'))
        candidate = self.manager.select(*self.position, assisted=self.window.assisted) if self.position else None
        expected = self.window.trial.expected if self.window.trial else None
        for t in self.manager.targets:
            rect = QRectF(t.x, t.y, t.width, t.height)
            if self.window.assisted:
                pad = self.manager.padding
                p.setPen(QPen(QColor('#477e9c'), 1, Qt.PenStyle.DashLine))
                p.setBrush(QColor('#182e44'))
                p.drawRoundedRect(rect.adjusted(-pad, -pad, pad, pad), 10, 10)
            p.setBrush(QColor('#285f56') if t.id == expected else QColor('#24364e'))
            p.setPen(QPen(QColor('#62e5be') if t.id == expected else QColor('#627b9d'), 2))
            p.drawRoundedRect(rect, 7, 7)
            p.setPen(QColor('#ffffff'))
            p.drawText(rect, Qt.AlignmentFlag.AlignCenter, t.label)
            if candidate and candidate.id == t.id:
                p.setPen(QPen(QColor('#f5c96a'), 2))
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.drawRoundedRect(rect.adjusted(-4, -4, 4, 4), 9, 9)
        if self.position:
            p.setPen(QPen(QColor('#f5c96a'), 2))
            p.setBrush(QColor('#f5c96a'))
            p.drawEllipse(QPointF(*self.position), 4, 4)
        p.end()


class Demo(QWidget):
    def __init__(self, controller=None):
        super().__init__()
        self.controller = controller
        self.assisted = False
        self.use_filter = False
        self.trial = None
        self.results = []
        self.setWindowTitle('SteadyHand | Targets & metrics')
        self.setStyleSheet('QWidget { background:#101c30; color:#e5edf7; font-size:14px; }'
                           'QPushButton,QComboBox { padding:9px; background:#24364e; border-radius:5px; }')
        layout = QVBoxLayout(self)
        title = QLabel('SteadyHand · Target practice')
        title.setStyleSheet('font-size:24px; font-weight:bold;')
        layout.addWidget(title)
        layout.addWidget(QLabel('Click the green target. Dashed boxes show expanded click areas; gold shows selection.'))
        row = QHBoxLayout()
        self.mode = QComboBox()
        self.mode.addItems(['Baseline', 'Target assistance'])
        if controller is not None:
            self.mode.addItem('Smoothing + target assistance')
        row.addWidget(self.mode)
        self.start = QPushButton('Start trial')
        self.start.clicked.connect(self.begin)
        row.addWidget(self.start)
        abort = QPushButton('Abort trial')
        abort.clicked.connect(self.abort)
        row.addWidget(abort)
        export = QPushButton('Export JSON')
        export.clicked.connect(self.export)
        row.addWidget(export)
        layout.addLayout(row)
        self.instruction = QLabel('Choose a mode and start. Each trial has 10 successful selections.')
        layout.addWidget(self.instruction)
        self.canvas = Canvas(self)
        layout.addWidget(self.canvas)
        self.stats = QLabel()
        layout.addWidget(self.stats)
        self.feedback = QLabel('Standalone target assistance works without Yee’s controller.')
        layout.addWidget(self.feedback)
        self.history = QLabel('Completed trials appear here.')
        self.history.setWordWrap(True)
        layout.addWidget(self.history)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh)
        self.timer.start(100)
        self.refresh()

    def begin(self):
        self.assisted = self.mode.currentIndex() > 0
        self.use_filter = self.mode.currentIndex() == 2
        if self.controller is not None:
            self.controller.enabled = self.use_filter
            self.controller.simulate_tremor = False
            if hasattr(self.controller, 'reset'):
                self.controller.reset()
            else:
                for name in ('fx', 'fy'):
                    f = getattr(self.controller, name)
                    setattr(self.controller, name, type(f)(min_cutoff=f.min_cutoff, beta=f.beta, d_cutoff=f.d_cutoff))
        self.trial = Trial(self.mode.currentText(), SEQUENCE)
        self.start.setEnabled(False)
        self.mode.setEnabled(False)
        self.feedback.setText('Select the green target; misses do not advance the task.')
        self.refresh()

    def abort(self):
        if self.trial and not self.trial.complete:
            self.trial = None
            self.feedback.setText('Trial discarded. Completed results are retained.')
        self.start.setEnabled(True)
        self.mode.setEnabled(True)
        self.refresh()

    def finish(self):
        self.results.append(self.trial)
        self.start.setEnabled(True)
        self.mode.setEnabled(True)
        self.feedback.setText('Trial complete. Try another mode with the same targets.')
        lines = []
        for t in self.results[-4:]:
            s = t.summary()
            lines.append(f"{s['mode']}: {s['accuracy']:.0%} accuracy · {s['misses']} misses · {s['seconds']:.1f}s")
        self.history.setText('\n'.join(lines))

    def refresh(self):
        if self.trial:
            s = self.trial.summary()
            accuracy = '—' if s['accuracy'] is None else f"{s['accuracy']:.0%}"
            self.stats.setText(f"Hits {s['hits']}   |   Misses {s['misses']}   |   Clicks {s['interactions']}   |   Accuracy {accuracy}   |   Time {s['seconds']:.1f}s")
            self.instruction.setText('Complete: 10 / 10' if self.trial.complete else
                                     f'Select: {self.trial.expected.upper()}   ·   {self.trial.index} / 10 complete')
        else:
            self.stats.setText('No active trial')
            self.instruction.setText('Choose a mode and start a trial.')
        self.canvas.update()

    def export(self):
        if not self.results:
            QMessageBox.information(self, 'No results', 'Complete a trial before exporting.')
            return
        path, _ = QFileDialog.getSaveFileName(self, 'Export completed trials', 'steadyhand-results.json', 'JSON (*.json)')
        if path:
            try:
                save_results(path, self.results)
                self.feedback.setText('Results exported.')
            except OSError as exc:
                QMessageBox.warning(self, 'Export failed', str(exc))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--yee', action='store_true', help='Use the existing project controller')
    args = parser.parse_args()
    controller = None
    if args.yee:
        try:
            from accessshift.modules.steadyhand.controller import SteadyHandController
            controller = SteadyHandController()
        except ImportError as exc:
            parser.error(f'Cannot import the project controller: {exc}. Run from GitHappens with steadyhand_demo alongside accessshift.')
    app = QApplication(sys.argv[:1])
    window = Demo(controller)
    window.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
