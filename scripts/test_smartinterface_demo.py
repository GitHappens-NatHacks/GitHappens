"""Local Qt smoke checks for SmartInterface Demo Lab.

From GitHappens repository root:
    python scripts/test_smartinterface_demo.py

This is a GUI test: use a computer with a graphical session and PySide6.
"""
from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication
from accessshift.ui.healthcare_demo_window import HealthcareDemoWindow

app = QApplication.instance() or QApplication([])
demo = HealthcareDemoWindow(repo_root=Path.cwd(), smart_interface_enabled=False)
demo.show()
app.processEvents()
assert not demo._accessible
assert demo.original_btn.isChecked()
assert len(demo.slots) == 6
assert demo.portal.minimumWidth() >= 1000
assert demo.scroll.horizontalScrollBarPolicy() == Qt.ScrollBarPolicy.ScrollBarAsNeeded

# Reproduce the recording: drag the original window narrower. Form content
# should remain its natural width, with scrolling instead of disappearing.
demo.resize(815, 600)
app.processEvents()
assert demo.portal.minimumWidth() >= 1000
assert demo.first.isVisible()
assert demo.department.isVisible()
assert demo.scroll.horizontalScrollBar().maximum() > 0, 'Dense portal should scroll when window shrinks'

demo.first.setText('Taylor')
demo.last.setText('Example')
demo.department.setCurrentText('Neurology')
demo.reason.setPlainText('Sample question')
demo._choose_time('11:00 AM')
field_object = demo.first

demo.set_accessible(True)
app.processEvents()
assert demo.first is field_object
assert demo.first.text() == 'Taylor'
assert demo.department.currentText() == 'Neurology'
assert demo.reason.toPlainText() == 'Sample question'
assert demo._selected_time == '11:00 AM'
assert demo.portal.minimumWidth() == 0
assert demo.sidebar.isHidden() and demo.notes.isHidden()
assert demo.first.isVisible()

demo._go_step(2)
app.processEvents()
assert demo.times.isVisible()
demo._go_step(3)
app.processEvents()
assert 'Taylor' in demo.summary.text()
assert '11:00 AM' in demo.summary.text()

demo.set_accessible(False)
app.processEvents()
assert demo.first is field_object
assert demo.first.text() == 'Taylor'
assert demo._selected_time == '11:00 AM'
assert 'background:#FFFFFF' in demo.styleSheet()
demo.close()
print('PASS: resize, scrolling, contrast, shared fields, same data, guided steps')
