"""The primary AccessShift application window.

Replaces the old healthcare booking front page with a cross-platform
accessibility control center.  Retains MainWindow(repo_root) for app.py.
"""
from accessshift.ui.control_center import MainWindow

__all__ = ['MainWindow']
