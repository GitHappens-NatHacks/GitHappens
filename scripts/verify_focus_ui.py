"""Capture actual local Qt screenshots to check alignment on your computer.

Run from the GitHappens repo with the working PySide6 environment active:
    python scripts/verify_focus_ui.py
"""
from pathlib import Path
from PySide6.QtWidgets import QApplication
from accessshift.ui.main_window import MainWindow
from accessshift.ui.control_center import UI_VERSION


def main():
    app = QApplication.instance() or QApplication([])
    repo = Path(__file__).resolve().parent.parent
    out = Path.home() / 'Desktop' / 'AccessShift_Focus_UI_2_0'
    out.mkdir(parents=True, exist_ok=True)
    w = MainWindow(repo_root=repo)
    w.show()
    assert 'Focus UI 2.0' in w.windowTitle(), w.windowTitle()
    assert UI_VERSION == 'FOCUS-2.0.0'
    views = [
        ('01_assist', 'home', None),
        ('02_settings_display', 'adjust', 'appearance'),
        ('03_settings_pointer', 'adjust', 'mouse'),
        ('04_settings_gaze', 'adjust', 'eyes'),
        ('05_settings_voice', 'adjust', 'voice'),
        ('06_demo', 'try', None),
    ]
    for name, nav, detail in views:
        w._navigate(nav, detail)
        app.processEvents()
        target = out / (name + '.png')
        assert w.grab().save(str(target)), target
        print(target)
    # Never write testing preferences or open camera/mouse services here.
    w.close()
    print('Screenshot check complete. UI version:', UI_VERSION)


if __name__ == '__main__':
    main()
