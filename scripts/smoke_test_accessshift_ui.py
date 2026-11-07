"""Minimal UI wiring smoke test, run from GitHappens repo root after installing dependencies.

    python scripts/smoke_test_accessshift_ui.py
No webcam, network, OS pointer permissions or pytest necessary.
"""
from __future__ import annotations

import sys
from pathlib import Path

repo = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(repo))

from PySide6.QtWidgets import QApplication
from accessshift.ui.main_window import MainWindow

app = QApplication.instance() or QApplication([])
window = MainWindow(repo)
assert len(window._pages) == 6
assert 'overview' in window._pages
assert window.engine is not None
assert window._sliders['tremor_strength'][0].minimum() == 0
assert window._sliders['gaze_dwell_ms'][0].maximum() == 2000
assert window.steady is not None
print('OK: AccessShift settings UI initialized; all 6 pages and engine connections exist.')
window.close()
