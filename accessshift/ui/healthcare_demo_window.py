"""SmartInterface healthcare demo: a practice appointment form, simplified or original.

Simplified: two calm steps (Your details, then Appointment) with a progress bar,
ending on a "Sample completed" screen. Original: the same four fields all at once.
The same input widgets are used in both views, so nothing typed is lost when
switching. Nothing is saved, sent or booked.

When SmartInterface is on in the person's profile, the form opens simplified and
follows their text size, colour theme and click target size live
(apply_preferences, connected to the control center's preferences_changed).
"""
from __future__ import annotations

import re
from pathlib import Path

from PySide6.QtCore import QPointF, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPalette, QPen
from PySide6.QtWidgets import (
    QComboBox, QDialog, QFrame, QGridLayout, QHBoxLayout, QLabel, QLineEdit,
    QProgressBar, QPushButton, QSizePolicy, QVBoxLayout, QWidget,
)

from accessshift.ui import theme as theme_mod

DEPARTMENTS = ('Primary care', 'Neurology', 'Cardiology', 'Physiotherapy')
TIMES = ('Wednesday 9:00 AM', 'Wednesday 10:30 AM', 'Thursday 1:00 PM', 'Friday 3:30 PM')
STEPS = (
    ('Your details', 'Enter the information you want to use in this sample.', 'Nothing is saved or submitted.'),
    ('Appointment', 'Choose a department and a sample time.', 'No booking will be made.'),
)
# Page background behind the white card, per colour theme.
CANVAS = {'standard': '#F4F8F6', 'warm': '#FFFBF2', 'cool': '#F4F8FD', 'high_contrast': '#0B0F0E'}
TRACK = {'standard': '#BCD5CE'}
DEFAULT_TEXT_PCT = 110  # the designs are drawn at the default text size


class _CheckBadge(QWidget):
    """Soft circle with a bold check mark, for the completed screen."""

    def __init__(self):
        super().__init__()
        self.setFixedSize(100, 100)
        self.fill = QColor('#E1F5EF')
        self.mark = QColor(theme_mod.DEEP_TEAL)

    def set_colors(self, fill: str, mark: str) -> None:
        self.fill, self.mark = QColor(fill), QColor(mark)
        self.update()

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(self.fill)
        p.drawEllipse(self.rect())
        pen = QPen(self.mark, 6)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        p.setPen(pen)
        p.drawPolyline([QPointF(35, 51), QPointF(46, 62), QPointF(66, 40)])
        p.end()


class HealthcareDemoWindow(QDialog):
    """Practice appointment form. Signals suit the team's gaze/metrics integrations."""

    mode_changed = Signal(bool)  # True = simplified, step-by-step view
    target_activated = Signal(str)
    demo_submitted = Signal(object)

    def __init__(
        self,
        repo_root: Path,
        smart_interface_enabled: bool = True,
        parent: QWidget | None = None,
        embedded: bool = False,
    ):
        super().__init__(parent)
        self.repo_root = Path(repo_root)
        self._embedded = bool(embedded)
        self._accessible = bool(smart_interface_enabled)  # simplified view
        self._step = 0
        self._done = False
        self._settings: dict = {}
        self._mode_inputs: tuple | None = None
        self._targets: dict[str, QPushButton] = {}
        self.setObjectName('healthDemo')
        self.setWindowTitle('Younify · Healthcare demo')
        self._build()
        if self._embedded:
            self.setWindowFlags(Qt.WindowType.Widget)
        else:
            self.resize(1120, 780)
        self.setMinimumSize(640, 560)
        self._render()
        self._restyle()

    # ------------------------------------------------------------------ layout
    @staticmethod
    def _label(text: str, name: str, wrap: bool = False) -> QLabel:
        item = QLabel(text)
        item.setObjectName(name)
        item.setWordWrap(wrap)
        return item

    def _button(self, text: str, name: str, target: str) -> QPushButton:
        b = QPushButton(text)
        b.setObjectName(name)
        b.setCursor(Qt.CursorShape.PointingHandCursor)
        b.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._targets[target] = b
        return b

    def _build(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(68, 30, 68, 46)
        outer.setSpacing(0)
        self.note = self._label('Practice only · no information is sent', 'hdNote')
        outer.addWidget(self.note)
        outer.addSpacing(22)

        header = QHBoxLayout()
        header.setSpacing(24)
        titles = QVBoxLayout()
        titles.setSpacing(20)
        self.title = self._label('Healthcare appointment', 'hdTitle', True)
        self.subtitle = self._label('Try a more readable, step-by-step form.', 'hdSub', True)
        titles.addWidget(self.title)
        titles.addWidget(self.subtitle)
        header.addLayout(titles, 1)
        self.view_toggle = self._button('View original form', 'hdSecondary', 'demo_view_original')
        self.view_toggle.setMinimumWidth(234)
        self.view_toggle.clicked.connect(lambda: self.set_accessible(False))
        header.addWidget(self.view_toggle, 0, Qt.AlignmentFlag.AlignTop)
        outer.addLayout(header)

        self.original_heading = self._label('Original form · all details at once', 'hdOriginal')
        self.original_box = QWidget()
        ol = QVBoxLayout(self.original_box)
        ol.setContentsMargins(0, 18, 0, 8)
        ol.addWidget(self.original_heading)
        outer.addWidget(self.original_box)

        self.progress_box = QWidget()
        pl = QVBoxLayout(self.progress_box)
        pl.setContentsMargins(0, 32, 0, 0)
        pl.setSpacing(18)
        self.step_label = self._label('', 'hdStep')
        self.progress = QProgressBar()
        self.progress.setObjectName('hdProgress')
        self.progress.setRange(0, len(STEPS))
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(5)
        self.progress.setAccessibleName('Form progress')
        pl.addWidget(self.step_label)
        pl.addWidget(self.progress)
        outer.addWidget(self.progress_box)
        outer.addSpacing(26)
        self.done_gap = QWidget()
        self.done_gap.setFixedHeight(18)  # the finished screen has no progress bar above its card
        outer.addWidget(self.done_gap)

        self.card = QFrame()
        self.card.setObjectName('hdCard')
        self.card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        cl = QVBoxLayout(self.card)
        cl.setContentsMargins(36, 30, 36, 22)
        cl.setSpacing(0)
        # form view
        self.form_view = QWidget()
        fl = QVBoxLayout(self.form_view)
        fl.setContentsMargins(0, 0, 0, 0)
        fl.setSpacing(0)
        self.section_box = QWidget()
        sl = QVBoxLayout(self.section_box)
        sl.setContentsMargins(0, 0, 0, 16)
        sl.setSpacing(14)
        self.section_title = self._label('', 'hdSection')
        self.section_desc = self._label('', 'hdDesc', True)
        sl.addWidget(self.section_title)
        sl.addWidget(self.section_desc)
        fl.addWidget(self.section_box)
        self.grid = QGridLayout()
        self.grid.setHorizontalSpacing(56)
        self.grid.setVerticalSpacing(0)
        fl.addLayout(self.grid)
        self.original_spacer = QWidget()
        self.original_spacer.setFixedHeight(100)  # the original card leaves room below its fields
        fl.addWidget(self.original_spacer)
        cl.addWidget(self.form_view)
        # completed view
        self.done_view = QWidget()
        dl = QVBoxLayout(self.done_view)
        dl.setContentsMargins(0, 16, 0, 62)
        dl.setSpacing(0)
        self.badge = _CheckBadge()
        dl.addWidget(self.badge, 0, Qt.AlignmentFlag.AlignHCenter)
        dl.addSpacing(26)
        self.done_title = self._label('Sample completed', 'hdDoneTitle')
        self.done_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        dl.addWidget(self.done_title)
        dl.addSpacing(29)
        self.done_desc = self._label('No appointment was booked. No information was sent.', 'hdDoneDesc', True)
        self.done_desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        dl.addWidget(self.done_desc)
        cl.addWidget(self.done_view)
        outer.addWidget(self.card)
        outer.addStretch(1)
        outer.addSpacing(20)

        footer = QHBoxLayout()
        footer.setSpacing(20)
        self.footer_note = self._label('', 'hdFootnote', True)
        footer.addWidget(self.footer_note, 1)
        self.back = self._button('Back', 'hdSecondary', 'demo_back')
        self.back.setMinimumWidth(146)
        self.back.clicked.connect(lambda: self._go_step(self._step - 1))
        self.primary = self._button('Continue', 'hdPrimary', 'demo_continue')
        self.primary.setMinimumWidth(250)
        self.primary.clicked.connect(self._primary_action)
        footer.addWidget(self.back)
        footer.addWidget(self.primary)
        outer.addLayout(footer)

        # One set of fields, placed differently in each view.
        self.name = QLineEdit()
        self.name.setObjectName('patient_full_name')
        self.name.setPlaceholderText('Enter a name')
        self.birth = QLineEdit()
        self.birth.setObjectName('patient_date_of_birth')
        self.birth.setPlaceholderText('YYYY-MM-DD')
        self.department = QComboBox()
        self.department.setObjectName('visit_department')
        self.department.addItems(DEPARTMENTS)
        self.department.setPlaceholderText('Choose a department')
        self.department.setCurrentIndex(-1)
        self.time = QComboBox()
        self.time.setObjectName('appointment_time')
        self.time.addItems(TIMES)
        self.time.setPlaceholderText('Choose a time')
        self.time.setCurrentIndex(-1)
        self.fields = []
        for text, field in (('Full name', self.name), ('Date of birth', self.birth),
                            ('Department', self.department), ('Appointment time', self.time)):
            lbl = self._label(text, 'hdField')
            lbl.setBuddy(field)
            field.setAccessibleName(text)
            field.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            self.fields.append((lbl, field))
        for combo in (self.department, self.time):
            combo.currentIndexChanged.connect(lambda _i, c=combo: self._mark_empty(c))
            self._mark_empty(combo)

    @staticmethod
    def _mark_empty(combo: QComboBox) -> None:
        combo.setProperty('empty', combo.currentIndex() < 0)
        combo.style().unpolish(combo)
        combo.style().polish(combo)

    def _place_fields(self) -> None:
        while self.grid.count():
            item = self.grid.takeAt(0)
            if item.widget() is not None:
                item.widget().hide()
        if self._done:
            return
        if self._accessible:
            chosen = self.fields[self._step * 2:self._step * 2 + 2]
            spots = [(lbl, field, i * 2, 0) for i, (lbl, field) in enumerate(chosen)]
            self.grid.setColumnStretch(1, 0)
        else:
            spots = [(lbl, field, (i // 2) * 2, i % 2) for i, (lbl, field) in enumerate(self.fields)]
            self.grid.setColumnStretch(1, 1)
        self.grid.setColumnStretch(0, 1)
        for lbl, field, row, col in spots:
            # a field's label sits close to it; the next label leaves a clear gap
            gap = 0 if row == 0 else (12 if self._accessible else 34)
            lbl.setContentsMargins(0, gap, 0, 8)
            self.grid.addWidget(lbl, row, col)
            self.grid.addWidget(field, row + 1, col)
            lbl.show()
            field.show()

    def _render(self) -> None:
        simplified, done = self._accessible, self._done
        self.view_toggle.setVisible(simplified and not done)
        self.original_box.setVisible(not simplified and not done)
        self.progress_box.setVisible(simplified and not done)
        self.form_view.setVisible(not done)
        self.done_view.setVisible(done)
        self.done_gap.setVisible(done)
        self.section_box.setVisible(simplified)
        self.original_spacer.setVisible(not simplified)
        self.back.setVisible(simplified and not done and self._step > 0)
        if done:
            self.footer_note.setText('You can close this demo window at any time.')
            self.primary.setText('Start again')
        elif simplified:
            title, desc, note = STEPS[self._step]
            self.section_title.setText(title)
            self.section_desc.setText(desc)
            self.footer_note.setText(note)
            self.step_label.setText(f'Step {self._step + 1} of {len(STEPS)}')
            self.progress.setValue(self._step + 1)
            self.primary.setText('Finish demo' if self._step == len(STEPS) - 1 else 'Continue')
        else:
            self.footer_note.setText('Use the simplified version to focus on one step at a time.')
            self.primary.setText('Try simplified')
        self.primary.setAccessibleName(self.primary.text())
        self._place_fields()

    # ------------------------------------------------------------------ actions
    def _primary_action(self) -> None:
        if self._done:
            self.reset()
        elif not self._accessible:
            self.set_accessible(True)
        elif self._step < len(STEPS) - 1:
            self._go_step(self._step + 1)
        else:
            self._finish()

    def _go_step(self, step: int) -> None:
        self._step = max(0, min(len(STEPS) - 1, step))
        self._render()
        if self._accessible and not self._done and self.isVisible():
            self.fields[self._step * 2][1].setFocus()

    def _finish(self) -> None:
        payload = {
            'full_name': self.name.text().strip(),
            'date_of_birth': self.birth.text().strip(),
            'department': self.department.currentText(),
            'time': self.time.currentText(),
            'simulation': True,
        }
        self._done = True
        self._render()
        self.demo_submitted.emit(payload)

    def reset(self) -> None:
        """Start again: empty fields, step 1."""
        self.name.clear()
        self.birth.clear()
        self.department.setCurrentIndex(-1)
        self.time.setCurrentIndex(-1)
        self._done = False
        self._go_step(0)

    # ------------------------------------------------------------------ public API
    def set_accessible(self, enabled: bool) -> None:
        """Simplified (True) or original (False) view of the same form."""
        enabled = bool(enabled)
        changed = enabled != self._accessible
        self._accessible = enabled
        if changed:
            self._done = False
        self._render()
        self._restyle()
        if changed:
            self.mode_changed.emit(enabled)

    def show_original(self, original: bool) -> None:
        self.set_accessible(not original)

    def toggle_mode(self) -> None:
        self.set_accessible(not self._accessible)

    def enter_baseline(self) -> None:
        self.set_accessible(False)

    def apply_preferences(self, settings: dict) -> None:
        """Follow the person's profile. Called on Qt's GUI thread via preferences_changed.

        The view only changes when SmartInterface (or the simplified layout) is switched,
        so adjusting text size never undoes a manual switch to the original form.
        """
        self._settings = dict(settings)
        inputs = (bool(settings.get('smart_interface', False)), bool(settings.get('reduce_complexity', True)))
        if inputs != self._mode_inputs:
            self._mode_inputs = inputs
            self.set_accessible(inputs[0] and inputs[1])
        else:
            self._restyle()

    def activate_target(self, target_id: str) -> bool:
        """Lets a gaze module press named on-screen buttons."""
        widget = self._targets.get(target_id)
        if widget is None or not widget.isVisible() or not widget.isEnabled():
            return False
        widget.click()
        self.target_activated.emit(target_id)
        return True

    # ------------------------------------------------------------------ styling
    def _restyle(self) -> None:
        s = self._settings
        smart = bool(s.get('smart_interface', False))
        profile = str(s.get('color_profile', 'standard')) if smart else 'standard'
        t = theme_mod.theme(profile)
        canvas = CANVAS.get(profile, t.bg)
        track = TRACK.get(profile, t.border)
        field_border = '#B9D0CA' if profile == 'standard' else t.border
        target = max(1.0, int(s.get('target_size_pct', 140)) / 140.0) if smart else 1.0
        field_h = round(60 * target)
        button_h = round(58 * target)
        qss = f'''
QDialog#healthDemo {{ background: {canvas}; }}
QLabel {{ background: transparent; color: {t.text}; }}
QLabel#hdNote {{ color: {t.text}; font-size: 15px; }}
QLabel#hdTitle {{ color: {t.heading}; font-size: 32px; font-weight: 700; }}
QLabel#hdSub {{ color: {t.muted}; font-size: 17px; }}
QLabel#hdOriginal {{ color: {t.heading}; font-size: 22px; font-weight: 700; }}
QLabel#hdStep {{ color: {t.primary}; font-size: 17px; font-weight: 700; }}
QProgressBar#hdProgress {{ background: {track}; border: none; border-radius: 2px; }}
QProgressBar#hdProgress::chunk {{ background: {t.primary}; border-radius: 2px; }}
QFrame#hdCard {{ background: {t.card}; border: none; border-radius: 14px; }}
QLabel#hdSection {{ color: {t.heading}; font-size: 24px; font-weight: 600; }}
QLabel#hdDesc {{ color: {t.muted}; font-size: 16px; }}
QLabel#hdField {{ color: {t.heading}; font-size: 17px; font-weight: 700; }}
QLabel#hdDoneTitle {{ color: {t.heading}; font-size: 28px; font-weight: 700; }}
QLabel#hdDoneDesc {{ color: {t.muted}; font-size: 17px; }}
QLabel#hdFootnote {{ color: {t.muted}; font-size: 16px; }}
QLineEdit, QComboBox {{ background: {t.card}; color: {t.text}; border: 1px solid {field_border};
    border-radius: 10px; padding: 0 18px; font-size: 17px;
    min-height: {field_h}px; max-height: {field_h}px; selection-background-color: {t.primary}; }}
QComboBox[empty="true"] {{ color: {t.muted}; }}
QLineEdit:focus, QComboBox:focus {{ border: 2px solid {t.active}; }}
QComboBox::drop-down {{ border: none; width: 36px; }}
QComboBox QAbstractItemView {{ background: {t.card}; color: {t.text}; selection-background-color: {t.mint};
    selection-color: {t.heading}; font-size: 17px; }}
QPushButton#hdPrimary {{ background: {t.primary}; color: {t.on_primary}; border: 2px solid {t.primary};
    border-radius: 10px; font-size: 16px; font-weight: 700; padding: 0 28px;
    min-height: {button_h}px; max-height: {button_h}px; }}
QPushButton#hdPrimary:hover {{ background: {t.primary_hover}; border-color: {t.primary_hover}; }}
QPushButton#hdSecondary {{ background: {t.card}; color: {t.primary}; border: 1px solid {field_border};
    border-radius: 10px; font-size: 16px; font-weight: 700; padding: 0 24px; }}
QPushButton#hdSecondary:hover {{ border-color: {t.primary}; }}
QPushButton:focus {{ border: 2px solid {t.active}; }}
'''
        pct = int(s.get('font_size_pct', DEFAULT_TEXT_PCT)) if smart else DEFAULT_TEXT_PCT
        scale = max(90, min(160, pct)) / DEFAULT_TEXT_PCT
        qss = re.sub(r'font-size:\s*(\d+)px', lambda m: f'font-size: {max(11, round(int(m.group(1)) * scale))}px', qss)
        self.setStyleSheet(qss)
        self.back.setFixedHeight(button_h)
        self.view_toggle.setFixedHeight(round(48 * target))
        self.badge.set_colors('#E1F5EF' if profile == 'standard' else t.mint, t.primary)
        for _lbl, field in self.fields:
            pal = field.palette()
            pal.setColor(QPalette.ColorRole.PlaceholderText, QColor(t.muted))
            field.setPalette(pal)
