"""Application entry: load env, start Qt event loop."""

from __future__ import annotations

import sys
from pathlib import Path

from dotenv import load_dotenv
from PySide6.QtWidgets import QApplication

from accessshift.ui.main_window import MainWindow


def run() -> int:
    root = Path(__file__).resolve().parents[1]
    load_dotenv(root / ".env")

    app = QApplication(sys.argv)
    app.setApplicationName("AccessShift AI")
    app.setOrganizationName("GitHappens")

    window = MainWindow(repo_root=root)
    window.show()
    return app.exec()
