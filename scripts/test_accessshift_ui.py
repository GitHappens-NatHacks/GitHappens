"""Optional integration smoke test. Execute from the GitHappens repository root.

    source ~/.venvs/accessshift/bin/activate
    python scripts/test_accessshift_ui.py

Uses mocked persistence so testing never modifies the person's saved settings.
On CI, run with QT_QPA_PLATFORM=offscreen if a Qt offscreen plugin is present.
"""
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

import accessshift.ui.control_center as control_center
from accessshift.ui.control_center_settings import AccessibilitySettings
from accessshift.ui.main_window import MainWindow

control_center.load_settings = lambda: AccessibilitySettings(initial_setup_complete=True)
control_center.save_settings = lambda _prefs: None

app = QApplication.instance() or QApplication([])
window = MainWindow(repo_root=Path.cwd())
window.show()
app.processEvents()

assert set(window._pages) == {'overview', 'personalize', 'gaze', 'steady', 'interface', 'speech', 'test'}
assert window._pages['interface'] is not window._pages['speech']
assert not window.tint_manager.active
assert len(window.tint_manager._windows) == 1
assert all(overlay.parentWidget() is window for overlay in window.tint_manager._windows.values())

window._open_healthcare_demo()
app.processEvents()
demo = window._healthcare_demo
assert demo is not None and demo.isVisible()
assert window.stack.currentWidget() is window._pages['interface']
assert len(window.tint_manager._windows) == 2
assert all(overlay.parentWidget() in (window, demo) for overlay in window.tint_manager._windows.values())
assert all(overlay.testAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
           for overlay in window.tint_manager._windows.values())
assert all(not overlay.isWindow() for overlay in window.tint_manager._windows.values())

demo.first.setText('Taylor')
demo._choose_time('11:00 AM')
window._change_option('font_size_pct', 140)
app.processEvents()
assert demo._visual_settings['font_size_pct'] == 140
assert demo.first.text() == 'Taylor' and demo._selected_time == '11:00 AM'

window._set_screen_tint(True)
app.processEvents()
assert window.tint_manager.active
assert all(overlay.isVisible() for overlay in window.tint_manager._windows.values())
window.tint_manager.update(color='rose', opacity=13)
assert window.tint_manager._opacity == 13
window._set_screen_tint(False)
assert not window.tint_manager.active
assert all(not overlay.isVisible() for overlay in window.tint_manager._windows.values())

demo.close()
window.close()
print('PASS: navigation, local-only tint, live demo synchronization and preserved form values')
