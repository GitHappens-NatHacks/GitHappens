"""Local GUI smoke test for the two-window SmartInterface demo.

Run from the GitHappens repository root using the SAME environment as the app:
    python scripts/test_smartinterface_live_preview.py

Use QT_QPA_PLATFORM=offscreen for headless automation if your Qt install supports it.
"""
from pathlib import Path
from PySide6.QtWidgets import QApplication
from accessshift.ui.healthcare_demo_window import HealthcareDemoWindow

app = QApplication.instance() or QApplication([])
demo = HealthcareDemoWindow(repo_root=Path.cwd(), smart_interface_enabled=False)
demo.show()
app.processEvents()

assert not demo._accessible
assert not hasattr(demo, 'original_btn')  # controls belong in the FIRST window
assert len(demo.slots) == 6
assert demo.portal.minimumWidth() >= 1000

demo.first.setText('Taylor')
demo.last.setText('Example')
demo.reason.setPlainText('A fictional check-up')
demo.department.setCurrentText('Neurology')
demo._choose_time('11:00 AM')
first_object = demo.first

settings = {
    'smart_interface': True,
    'reduce_complexity': True,
    'font_size_pct': 150,
    'target_size_pct': 170,
    'letter_spacing_px': 2,
    'color_profile': 'high_contrast',
}
demo.apply_preferences(settings)
app.processEvents()
assert demo._accessible
assert demo._simplify
assert demo.sidebar.isHidden() and demo.notes.isHidden()
assert demo.times.isHidden()  # guided step 0
assert demo.first is first_object and demo.first.text() == 'Taylor'
assert demo._selected_time == '11:00 AM'
assert '150%' in demo.mode_status.text()
assert '170%' in demo.mode_status.text()
assert '#090C14' in demo.styleSheet()
assert demo.slots[0].minimumHeight() > 58
assert 'Taylor' in demo.summary.text()

settings['font_size_pct'] = 100
settings['color_profile'] = 'warm'
demo.apply_preferences(settings)
app.processEvents()
assert '#FFF7EA' in demo.styleSheet()
assert demo.first.text() == 'Taylor' and demo._selected_time == '11:00 AM'
settings['reduce_complexity'] = False
demo.apply_preferences(settings)
app.processEvents()
assert not demo.sidebar.isHidden() and not demo.notes.isHidden()
assert demo.times.isVisible()
assert demo.portal.minimumWidth() >= 1000  # prevent clipping on dense layout

settings['smart_interface'] = False
demo.apply_preferences(settings)
app.processEvents()
assert not demo._accessible
assert demo.first.text() == 'Taylor'
assert demo._selected_time == '11:00 AM'
assert demo.portal.minimumWidth() >= 1000

demo.enter_baseline()
assert 'ORIGINAL FORM' in demo.mode_status.text()
demo.close()
print('PASS: live settings, theme, target size, complexity, preserved form data, baseline')
