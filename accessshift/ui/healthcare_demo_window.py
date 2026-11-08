"""SmartInterface Demo Lab: the *same* local form, before and after adaptation.

One set of Qt input widgets is reused in both modes. A user can type in the
original dense portal, turn SmartInterface on, and continue with the exact same
values. No data is transmitted; no third-party websites are modified.

Compatible with accessshift.ui.main_window.MainWindow's existing launcher:
    HealthcareDemoWindow(repo_root, smart_interface_enabled=True, parent=self)
"""
from __future__ import annotations

from pathlib import Path
import re

from PySide6.QtGui import QFont

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QFrame, QGridLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QScrollArea, QSizePolicy,
    QTextEdit, QVBoxLayout, QWidget,
)


NAVY = '#0B1F3A'
DARK = '#0B1F3A'


class HealthcareDemoWindow(QDialog):
    """A transform-in-place, fully local appointment demonstration.

    Signals are suitable for the team's gaze/metrics integrations. No camera,
    OS pointer, speech or network service is started by this window.
    """

    mode_changed = Signal(bool)
    target_activated = Signal(str)
    demo_submitted = Signal(object)

    def __init__(
        self,
        repo_root: Path,
        smart_interface_enabled: bool = True,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.repo_root = Path(repo_root)
        self._accessible = False
        self._simplify = True
        self._visual_settings = {}
        self._preview_live = False
        self._step = 0
        self._selected_time = '10:30 AM'
        self._targets: dict[str, QPushButton] = {}
        self._build_ui()
        self.set_accessible(False)  # start as original baseline, then listen for edits
        self.setWindowTitle('AccessShift AI — SmartInterface Demo Lab')
        # Keep controls usable when the window is dragged smaller.
        # A narrow original portal scrolls instead of crushing form fields.
        self.resize(1170, 800)
        self.setMinimumSize(650, 500)

    # ---------- Reusable visual helpers ----------
    @staticmethod
    def _label(text: str, name: str = '', wrap: bool = False) -> QLabel:
        result = QLabel(text)
        if name:
            result.setObjectName(name)
        result.setWordWrap(wrap)
        return result

    @staticmethod
    def _frame(name: str, *, padding: int = 16, spacing: int = 10):
        result = QFrame()
        result.setObjectName(name)
        layout = QVBoxLayout(result)
        layout.setContentsMargins(padding, padding, padding, padding)
        layout.setSpacing(spacing)
        return result, layout

    def _make_button(self, text: str, name: str, target: str = '') -> QPushButton:
        b = QPushButton(text)
        b.setObjectName(name)
        b.setCursor(Qt.CursorShape.PointingHandCursor)
        b.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        b.setAccessibleName(text)
        if target:
            self._targets[target] = b
        return b

    def _build_ui(self):
        self.setObjectName('smartDemo')
        outer = QVBoxLayout(self)
        outer.setContentsMargins(21, 18, 21, 15)
        outer.setSpacing(12)

        # Header clearly identifies this as a demonstration, not a patient app.
        header = QHBoxLayout()
        headings = QVBoxLayout()
        headings.setSpacing(3)
        headings.addWidget(self._label('Live preview · same healthcare form', 'pageTitle'))
        headings.addWidget(self._label(
            'Leave this window open. Change SmartInterface settings in AccessShift; this exact form updates live.',
            'subheading', True))
        header.addLayout(headings, 1)
        tag = self._label('Local simulation · no data sent', 'demoBadge')
        header.addWidget(tag, 0, Qt.AlignmentFlag.AlignTop)
        outer.addLayout(header)

        # One display-only status strip: all switches and sliders live in the
        # FIRST window (AccessShift Settings), never in this demo.
        toggler, tlay = self._frame('toggleSurface', padding=12, spacing=8)
        live_row = QHBoxLayout()
        live_row.addWidget(self._label('Live from AccessShift settings', 'subheading'))
        live_row.addStretch(1)
        self.mode_tag = self._label('Original baseline', 'modeTag')
        live_row.addWidget(self.mode_tag)
        tlay.addLayout(live_row)
        self.mode_status = self._label(
            'This is the complicated original form. Change a preference in the AccessShift window to transform it.',
            'modeDescription', True)
        tlay.addWidget(self.mode_status)
        outer.addWidget(toggler)

        # The comparison is narrated on screen, so judges see what changed.
        changes = QHBoxLayout()
        changes.setSpacing(8)
        self.chip_clutter = self._label('', 'changeChip')
        self.chip_size = self._label('', 'changeChip')
        self.chip_flow = self._label('', 'changeChip')
        for chip in (self.chip_clutter, self.chip_size, self.chip_flow):
            changes.addWidget(chip)
        changes.addStretch(1)
        outer.addLayout(changes)

        # Portal is always the SAME form. Sections / widgets are never rebuilt.
        self.scroll = QScrollArea()
        self.scroll.setObjectName('portalScroll')
        self.scroll.setWidgetResizable(True)
        self.scroll.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        # Never cut off controls as the demo window is resized: on compact
        # windows the dense original portal may need horizontal scrolling.
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        outer.addWidget(self.scroll, 1)

        self.portal = QWidget()
        self.portal.setObjectName('portalRoot')
        portal_l = QVBoxLayout(self.portal)
        portal_l.setContentsMargins(14, 14, 14, 16)
        portal_l.setSpacing(13)

        top, top_l = self._frame('portalHeader', padding=17, spacing=6)
        topline = QHBoxLayout()
        brand = self._label('✚  NORTHHEALTH', 'portalBrand')
        topline.addWidget(brand)
        topline.addStretch(1)
        topline.addWidget(self._label('Patient portal  /  Appointments', 'portalPath'))
        top_l.addLayout(topline)
        top_l.addWidget(self._label('Schedule a healthcare appointment', 'portalTitle'))
        top_l.addWidget(self._label(
            'Sample appointment data only. This is not connected to a clinic.', 'portalSub'))
        portal_l.addWidget(top)

        self.progress_row = QHBoxLayout()
        self.progress_row.setSpacing(6)
        self.step_labels = []
        for i, name in enumerate(('1  Patient', '2  Visit', '3  Time', '4  Review')):
            chip = self._label(name, 'stepChip')
            self.step_labels.append(chip)
            self.progress_row.addWidget(chip)
        portal_l.addLayout(self.progress_row)

        body = QHBoxLayout()
        body.setSpacing(13)
        portal_l.addLayout(body, 1)

        self.sidebar, side_l = self._frame('sidePanel', padding=14, spacing=12)
        self.sidebar.setFixedWidth(175)
        side_l.addWidget(self._label('OTHER SERVICES', 'sideHeading'))
        for name in ('Medical records', 'Prescriptions', 'Lab results', 'Insurance', 'Billing', 'Message a clinic'):
            side_l.addWidget(self._label(name, 'sideText'))
        side_l.addStretch()
        body.addWidget(self.sidebar)

        self.center = QFrame()
        self.center.setObjectName('centerPane')
        self.center.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        center_l = QVBoxLayout(self.center)
        center_l.setContentsMargins(0, 0, 0, 0)
        center_l.setSpacing(11)
        body.addWidget(self.center, 1)

        self.patient, patient_l = self._frame('sectionCard', padding=17, spacing=10)
        patient_l.addWidget(self._label('Patient information', 'sectionTitle'))
        self.patient_subtitle = self._label('Complete the patient details below.', 'sectionHint', True)
        patient_l.addWidget(self.patient_subtitle)
        self.patient_grid = QGridLayout()
        self.patient_grid.setHorizontalSpacing(10)
        self.patient_grid.setVerticalSpacing(8)
        self.first = QLineEdit('Alex')
        self.last = QLineEdit('Morgan')
        self.birth = QLineEdit('1990-01-20')
        self.first.setObjectName('patient_first_name')
        self.last.setObjectName('patient_last_name')
        self.birth.setObjectName('patient_date_of_birth')
        self.birth.setPlaceholderText('YYYY-MM-DD (fictional)')
        self.patient_fields = [
            (self._label('First name', 'fieldLabel'), self.first),
            (self._label('Last name', 'fieldLabel'), self.last),
            (self._label('Date of birth', 'fieldLabel'), self.birth),
        ]
        patient_l.addLayout(self.patient_grid)
        center_l.addWidget(self.patient)

        self.visit, visit_l = self._frame('sectionCard', padding=17, spacing=10)
        visit_l.addWidget(self._label('Appointment details', 'sectionTitle'))
        visit_l.addWidget(self._label('Select a department and describe your visit.', 'sectionHint', True))
        self.visit_grid = QGridLayout()
        self.visit_grid.setHorizontalSpacing(10)
        self.visit_grid.setVerticalSpacing(8)
        self.department = QComboBox()
        self.department.addItems(['Primary care', 'Neurology', 'Cardiology', 'Physiotherapy'])
        self.department.setObjectName('visit_department')
        self.doctor = QComboBox()
        self.doctor.addItems(['Dr. Singh', 'Dr. Okonkwo', 'NP Alvarez'])
        self.doctor.setObjectName('visit_provider')
        self.reason = QTextEdit('Routine check-up')
        self.reason.setObjectName('visit_reason')
        self.reason.setAcceptRichText(False)
        self.visit_fields = [
            (self._label('Department', 'fieldLabel'), self.department),
            (self._label('Provider', 'fieldLabel'), self.doctor),
            (self._label('Reason for visit', 'fieldLabel'), self.reason),
        ]
        visit_l.addLayout(self.visit_grid)
        center_l.addWidget(self.visit)

        self.times, times_l = self._frame('sectionCard', padding=17, spacing=11)
        times_l.addWidget(self._label('Available times', 'sectionTitle'))
        times_l.addWidget(self._label('Sample availability · Wednesday, November 11', 'sectionHint'))
        self.slot_grid = QGridLayout()
        self.slot_grid.setSpacing(8)
        self.slots = []
        for t in ('9:00 AM', '9:30 AM', '10:00 AM', '10:30 AM', '11:00 AM', '11:30 AM'):
            ident = 'appointment_time_' + t.replace(' ', '').replace(':', '').lower()
            b = self._make_button(t, 'timeButton', ident)
            b.setCheckable(True)
            b.clicked.connect(lambda checked=False, value=t: self._choose_time(value))
            self.slots.append(b)
        times_l.addLayout(self.slot_grid)
        center_l.addWidget(self.times)

        self.review, review_l = self._frame('sectionCard', padding=18, spacing=11)
        review_l.addWidget(self._label('Review the same appointment', 'sectionTitle'))
        review_l.addWidget(self._label('Nothing was lost when SmartInterface changed the layout.', 'sectionHint', True))
        self.summary = self._label('', 'reviewSummary', True)
        review_l.addWidget(self.summary)
        center_l.addWidget(self.review)

        self.consent = QCheckBox('This is a sample request — no real appointment will be created')
        self.consent.setChecked(True)
        self.consent.setObjectName('consent_confirmation')
        center_l.addWidget(self.consent)

        actions = QHBoxLayout()
        self.back = self._make_button('←  Back', 'neutralButton', 'demo_back')
        self.next = self._make_button('Continue  →', 'primaryButton', 'demo_continue')
        self.submit = self._make_button('Submit sample request', 'primaryButton', 'demo_submit')
        self.back.clicked.connect(lambda: self._go_step(self._step - 1))
        self.next.clicked.connect(lambda: self._go_step(self._step + 1))
        self.submit.clicked.connect(self._submit)
        actions.addWidget(self.back)
        actions.addStretch(1)
        actions.addWidget(self.next)
        actions.addWidget(self.submit)
        center_l.addLayout(actions)

        self.success = self._label('', 'successText', True)
        center_l.addWidget(self.success)

        self.notes, notes_l = self._frame('sidePanel', padding=14, spacing=10)
        self.notes.setFixedWidth(176)
        notes_l.addWidget(self._label('PATIENT NOTICE', 'sideHeading'))
        notes_l.addWidget(self._label('Online requests are reviewed by a care team.', 'sideText', True))
        notes_l.addWidget(self._label('Have your details ready before you submit.', 'sideText', True))
        notes_l.addStretch(1)
        body.addWidget(self.notes)

        bottom = self._label(
            'AccessShift changes the presentation of this same local form. No medical records, '
            'real appointments, browser extensions or third-party websites are involved.',
            'footerText', True)
        outer.addWidget(bottom)

        # Install the scroll-area content AFTER its layout and child widgets
        # have been created. Qt documents that doing this in reverse can
        # leave a scroll area blank or with stale geometry.
        self.scroll.setWidget(self.portal)

        # No duplicate fields. Mode changes only relayout/visibility/sizes.
        self._choose_time(self._selected_time)
        self._arrange_form_fields(False)
        self._arrange_slots(False)
        self._update_summary()
        self.first.textChanged.connect(self._update_summary)
        self.last.textChanged.connect(self._update_summary)
        self.birth.textChanged.connect(self._update_summary)
        self.reason.textChanged.connect(self._update_summary)
        self.department.currentTextChanged.connect(self._update_summary)
        self.doctor.currentTextChanged.connect(self._update_summary)
        self._styling(False)

    def _arrange_grid(self, grid: QGridLayout, fields: list, accessible: bool):
        # Moving an existing QWidget in QGridLayout does not recreate it or
        # discard its text, selection, focus handlers or signal connections.
        while grid.count():
            grid.takeAt(0)
        if accessible:
            for i, (label, control) in enumerate(fields):
                grid.addWidget(label, i * 2, 0)
                grid.addWidget(control, i * 2 + 1, 0)
            grid.setColumnStretch(0, 1)
            grid.setColumnStretch(1, 0)
            grid.setColumnStretch(2, 0)
            grid.setColumnStretch(3, 0)
        else:
            for i, (label, control) in enumerate(fields):
                col = (i % 2) * 2
                row = i // 2
                grid.addWidget(label, row, col)
                grid.addWidget(control, row, col + 1)
            grid.setColumnStretch(0, 0)
            grid.setColumnStretch(1, 1)
            grid.setColumnStretch(2, 0)
            grid.setColumnStretch(3, 1)

    def _arrange_form_fields(self, accessible: bool):
        self._arrange_grid(self.patient_grid, self.patient_fields, accessible)
        self._arrange_grid(self.visit_grid, self.visit_fields, accessible)
        size_pct = int(self._visual_settings.get('target_size_pct', 140))
        scale = max(1.0, min(2.0, size_pct / 100.0))
        self.reason.setFixedHeight(max(110, round(80 * scale)) if accessible else 58)
        height = max(52, round(40 * scale)) if accessible else 35
        for w in (self.first, self.last, self.birth, self.department, self.doctor):
            w.setMinimumHeight(height)
            w.setMaximumHeight(height)

    def _arrange_slots(self, accessible: bool):
        while self.slot_grid.count():
            self.slot_grid.takeAt(0)
        cols = 2 if accessible else 6
        size_pct = int(self._visual_settings.get('target_size_pct', 140))
        button_height = max(54, round(42 * max(1.0, min(2.0, size_pct / 100.0)))) if accessible else 32
        for i, b in enumerate(self.slots):
            self.slot_grid.addWidget(b, i // cols, i % cols)
            b.setMinimumHeight(button_height)
            b.setMaximumHeight(button_height)
        for c in range(6):
            self.slot_grid.setColumnStretch(c, 1 if c < cols else 0)

    def _choose_time(self, time: str):
        self._selected_time = time
        for b in self.slots:
            b.setChecked(b.text() == time)
        self._update_summary()
        self.target_activated.emit('appointment_time_' + time.replace(' ', '').replace(':', '').lower())

    def _update_summary(self, *_):
        if not hasattr(self, 'summary'):
            return
        self.summary.setText(
            f'Patient: {self.first.text().strip()} {self.last.text().strip()}\n'
            f'Date of birth: {self.birth.text().strip()}\n'
            f'Department: {self.department.currentText()}\n'
            f'Provider: {self.doctor.currentText()}\n'
            f'Appointment: Wednesday, November 11 · {self._selected_time}\n'
            f'Reason: {self.reason.toPlainText().strip()}'
        )

    def enter_baseline(self) -> None:
        """Opening the demo starts with the unchanged form, regardless of saved defaults.

        The first deliberate edit in the separate control center applies ALL
        active settings and from then on every change is reflected live.
        """
        self._preview_live = False
        self._visual_settings = {}
        self._simplify = True
        self.set_accessible(False)
        self.mode_status.setText(
            'ORIGINAL FORM — Now use the first AccessShift window to change text size, colour, '
            'target size, or toggle SmartInterface. This preview updates automatically.')

    def apply_preferences(self, settings: dict) -> None:
        """Called by MainWindow.preferences_changed on Qt's GUI thread.

        The same QLineEdit/QComboBox/QTextEdit/QPushButton objects remain alive;
        their data never gets copied to a different form.
        """
        self._preview_live = True
        self._visual_settings = dict(settings)
        self._simplify = bool(settings.get('reduce_complexity', True))
        self.set_accessible(bool(settings.get('smart_interface', False)))

    def set_accessible(self, enabled: bool):
        """Update the *same* form in place, not a different page."""
        old_mode = self._accessible
        self._accessible = bool(enabled)
        guided = self._accessible and self._simplify
        if guided and not old_mode:
            self._step = 0
        self._arrange_form_fields(self._accessible)
        self._arrange_slots(self._accessible)
        self.portal.setMinimumWidth(0 if guided else 1030)
        self.sidebar.setVisible(not guided)
        self.notes.setVisible(not guided)
        if self._accessible:
            font_pct = int(self._visual_settings.get('font_size_pct', 110))
            target_pct = int(self._visual_settings.get('target_size_pct', 140))
            tone = str(self._visual_settings.get('color_profile', 'standard')).replace('_',' ')
            spacing = int(self._visual_settings.get('letter_spacing_px', 0))
            self.mode_status.setText(
                'LIVE ADAPTATION — This is the same form: text ' + str(font_pct) + '%, '
                + 'targets ' + str(target_pct) + '%, ' + tone + ' colours, '
                + str(spacing) + ' px letter spacing. '
                + ('Guided steps and reduced clutter are on.' if guided else
                   'All sections stay visible (reduce complexity is off).'))
            self.mode_tag.setText('SMARTINTERFACE ON')
            self.chip_clutter.setText('2 sidebars hidden' if guided else 'Sidebars visible')
            self.chip_size.setText('Targets ' + str(target_pct) + '%')
            self.chip_flow.setText('Guided steps' if guided else 'All sections visible')
        else:
            self.mode_status.setText(
                'ORIGINAL PORTAL — SmartInterface is off. Toggle it on in the AccessShift '
                'settings window, or change another preference while it is enabled.')
            self.mode_tag.setText('ORIGINAL FORM')
            self.chip_clutter.setText('2 extra sidebars')
            self.chip_size.setText('Compact targets')
            self.chip_flow.setText('All sections visible')
        previous_scroll = self.scroll.verticalScrollBar().value()
        self._go_step(self._step if guided else 0)
        self._styling(self._accessible)
        if old_mode == self._accessible:
            self.scroll.verticalScrollBar().setValue(previous_scroll)
        self.portal.updateGeometry()
        self.scroll.widget().updateGeometry()
        self.mode_changed.emit(self._accessible)
        if old_mode != self._accessible:
            self.scroll.verticalScrollBar().setValue(0)

    def toggle_mode(self) -> None:
        """Legacy compatibility: prefer changing AccessShift's SmartInterface switch."""
        self.set_accessible(not self._accessible)

    def _go_step(self, step: int) -> None:
        self._step = max(0, min(3, step))
        guided = self._accessible and self._simplify
        for i, section in enumerate((self.patient, self.visit, self.times, self.review)):
            section.setVisible((i == self._step) if guided else (i < 3))
        self.progress_row_visibility(guided)
        self.back.setVisible(guided and self._step > 0)
        self.next.setVisible(guided and self._step < 3)
        self.submit.setVisible((not guided) or self._step == 3)
        self.consent.setVisible((not guided) or self._step == 3)
        self._update_summary()
        for i, label in enumerate(self.step_labels):
            label.setProperty('stepState', 'current' if i == self._step else 'other')
            label.setStyleSheet(
                'background:#D6E8F8; color:#0B1F3A; border-radius:8px; padding:9px; '
                'font-weight:700;' if i == self._step else
                'background:#F4F7FB; color:#5A6F8A; border-radius:8px; padding:9px;'
            )
        self.scroll.verticalScrollBar().setValue(0)

    def progress_row_visibility(self, show: bool):
        # A QLayout cannot be hidden; hide its constituent labels instead.
        for item in self.step_labels:
            item.setVisible(show)

    def _submit(self):
        if not (self.first.text().strip() and self.last.text().strip()):
            self.success.setText('Enter a first and last name to continue.')
            return
        if not self.consent.isChecked():
            self.success.setText('Confirm that this is a simulation first.')
            return
        payload = {
            'first_name': self.first.text().strip(),
            'last_name': self.last.text().strip(),
            'date_of_birth': self.birth.text().strip(),
            'department': self.department.currentText(),
            'provider': self.doctor.currentText(),
            'time': self._selected_time,
            'reason': self.reason.toPlainText().strip(),
            'simulation': True,
        }
        self.success.setText('✓  Sample request completed locally. No information was sent.')
        self.demo_submitted.emit(payload)
        from accessshift.ui.booking_confirmation import BookingConfirmationDialog
        when = f'Wednesday, November 11 · {self._selected_time}'
        visit = self.department.currentText() or 'Visit'
        who = f'{payload["first_name"]} {payload["last_name"]}'.strip() or 'you'
        BookingConfirmationDialog(who=who, visit=visit, when=when, parent=self).exec()

    def activate_target(self, target_id: str) -> bool:
        """Allows a future gaze module to press named on-screen targets."""
        widget = self._targets.get(target_id)
        if widget is None or not widget.isVisible() or not widget.isEnabled():
            return False
        widget.click()
        if not target_id.startswith('appointment_time_'):
            self.target_activated.emit(target_id)
        return True

    def _styling(self, accessible: bool):
        # Scoped at this dialog, without modifying the application's stylesheet.
        fs = 16 if accessible else 12
        field_font = 16 if accessible else 12
        title_font = 21 if accessible else 17
        style = '''
QDialog#smartDemo { background: #F5F5F7; color: #0B1F3A; }
QWidget#portalRoot { background: #F5F5F7; color: #0B1F3A; }
QScrollArea#portalScroll { border:1px solid #D7E0EC; border-radius:14px; background:#FFFFFF; }
QLabel { background:transparent; color:#0B1F3A; font-family:'Albert Sans', 'Avenir Next', Arial, sans-serif; }
QLabel#pageTitle { font-size:32px; font-weight:200; color:#0B1F3A; letter-spacing:-0.5px; }
QLabel#subheading { font-size:15px; color:#3E5370; }
QLabel#demoBadge { background:#E8F0FE; color:#0B1F3A; border:1px solid #C5D8F5;
    border-radius:999px; padding:8px 14px; font-size:13px; font-weight:600; }
QFrame#toggleSurface { background:#FFFFFF; border:1px solid #D7E0EC; border-radius:14px; }
QLabel#modeDescription { font-size:14px; color:#3E5370; }
QLabel#modeTag { background:#D6E8F8; color:#0B1F3A; border-radius:999px; padding:8px 14px; font-weight:650; font-size:13px; }
QLabel#changeChip { background:#FFFFFF; border:1px solid #D0DCEC; border-radius:999px;
    padding:8px 14px; color:#3E5370; font-size:13px; font-weight:500; }
QFrame#portalHeader { background:#FFFFFF; border:1px solid #D7E0EC; border-radius:12px; }
QLabel#portalBrand { color:#0B1F3A; font-size:16px; font-weight:650; }
QLabel#portalPath { color:#5A6F8A; font-size:13px; }
QLabel#portalTitle { color:#0B1F3A; font-size:22px; font-weight:650; }
QLabel#portalSub { color:#3E5370; font-size:13px; }
QFrame#sidePanel { background:#FFFFFF; border:1px solid #D7E0EC; border-radius:12px; }
QLabel#sideHeading { font-size:13px; color:#5A6F8A; font-weight:650; }
QLabel#sideText { color:#3E5370; font-size:13px; }
QFrame#sectionCard { background:#FFFFFF; border:1px solid #D7E0EC; border-radius:14px; }
QLabel#sectionHint { color:#3E5370; font-size:14px; }
QLabel#fieldLabel { color:#0B1F3A; font-size:''' + str(fs) + '''px; font-weight:600; }
QLabel#sectionTitle { color:#0B1F3A; font-size:''' + str(title_font) + '''px; font-weight:200; }
QLineEdit, QTextEdit, QComboBox {
    background:#FFFFFF; color:#0B1F3A; border:1px solid #B8C9DE; border-radius:10px;
    padding:8px 12px; font-size:''' + str(field_font) + '''px;
    selection-background-color:#D6E8F8; selection-color:#0B1F3A;
}
QLineEdit:focus, QTextEdit:focus, QComboBox:focus { border:2px solid #2F6FED; }
QComboBox QAbstractItemView { background:#FFFFFF; color:#0B1F3A; selection-background-color:#D6E8F8; }
QCheckBox { color:#0B1F3A; font-size:''' + str(fs) + '''px; spacing:9px; }
QPushButton { font-family:'Albert Sans', 'Avenir Next', Arial, sans-serif; border-radius:10px; font-weight:650; }
QPushButton#timeButton { color:#0B1F3A; background:#F4F7FB; border:1px solid #B8C9DE;
    padding:6px; font-size:''' + str(field_font) + '''px; }
QPushButton#timeButton:checked { color:#FFFFFF; background:#0B1F3A; border:2px solid #0B1F3A; }
QPushButton#timeButton:hover { background:#E8F0FE; color:#0B1F3A; }
QPushButton#timeButton:checked:hover { color:#FFFFFF; background:#123A6D; }
QPushButton#primaryButton { background:#0B1F3A; border:1px solid #0B1F3A;
    color:#FFFFFF; padding:12px 18px; font-size:''' + str(fs) + '''px; }
QPushButton#primaryButton:hover { background:#123A6D; }
QPushButton#neutralButton { background:#FFFFFF; border:1px solid #B8C9DE;
    color:#0B1F3A; padding:12px 18px; font-size:''' + str(fs) + '''px; }
QPushButton:focus { border:2px solid #2F6FED; }
QLabel#reviewSummary { background:#EAF1F8; border:1px solid #D0DCEC; border-radius:12px;
    color:#0B1F3A; font-size:''' + str(fs) + '''px; padding:16px; }
QLabel#successText { color:#0B3D6E; font-size:14px; font-weight:650; }
QLabel#footerText { color:#5A6F8A; font-size:13px; }
QScrollBar:vertical { background:#EAF1F8; width:10px; }
QScrollBar::handle:vertical { background:#B8C9DE; border-radius:5px; min-height:30px; }
'''
        if accessible:
            pct = max(90, min(160, int(self._visual_settings.get('font_size_pct', 110))))
            style = re.sub(r'font-size:\s*(\d+)px',
                           lambda m: f'font-size:{max(10, round(int(m.group(1)) * pct / 100))}px',
                           style)
            theme = str(self._visual_settings.get('color_profile', 'standard'))
            palettes = {
                'high_contrast': ('#050B16', '#0B1F3A', '#FFFFFF', '#2F6FED', '#FFFFFF', '#3E5370'),
                'warm': ('#F4F7FB', '#FFFFFF', '#0B1F3A', '#123A6D', '#FFFFFF', '#B8C9DE'),
                'cool': ('#EAF4FF', '#FFFFFF', '#16304A', '#2866CB', '#FFFFFF', '#B8D5F0'),
            }
            if theme in palettes:
                bg, panel, fg, accent, on_accent, border = palettes[theme]
                style += f'''
                QDialog#smartDemo, QWidget#portalRoot, QScrollArea#portalScroll {{ background:{bg}; color:{fg}; }}
                QFrame#portalHeader, QFrame#sidePanel, QFrame#sectionCard,
                QFrame#toggleSurface {{ background:{panel}; border:1px solid {border}; }}
                QLabel#portalBrand, QLabel#portalTitle, QLabel#sectionTitle,
                QLabel#fieldLabel, QLabel#portalPath, QLabel#portalSub, QLabel#sectionHint,
                QLabel#sideHeading, QLabel#sideText, QLabel#modeDescription,
                QLabel#changeChip, QLabel#footerText {{ color:{fg}; }}
                QLabel#changeChip, QLabel#modeTag {{ background:{panel}; border:1px solid {border}; color:{fg}; }}
                QLineEdit, QTextEdit, QComboBox {{ background:{panel}; color:{fg}; border:2px solid {border}; }}
                QComboBox QAbstractItemView {{ background:{panel}; color:{fg}; }}
                QCheckBox {{ color:{fg}; }}
                QPushButton#timeButton, QPushButton#neutralButton {{ background:{panel}; color:{fg}; border:2px solid {border}; }}
                QPushButton#primaryButton, QPushButton#timeButton:checked {{ background:{accent}; color:{on_accent}; border:2px solid {accent}; }}
                QLabel#reviewSummary {{ background:{panel}; color:{fg}; border:1px solid {border}; }}
                '''
        self.setStyleSheet(style)
        spacing = int(self._visual_settings.get('letter_spacing_px', 0)) if accessible else 0
        for widget in self.portal.findChildren(QWidget):
            if not isinstance(widget, (QLabel, QPushButton, QLineEdit, QComboBox, QTextEdit, QCheckBox)):
                continue
            font = QFont(widget.font())
            font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, max(0, min(4, spacing)))
            widget.setFont(font)
