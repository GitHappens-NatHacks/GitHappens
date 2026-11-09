"""Full-screen hands-free booking window for GazeControl.

Opened by the control center when "Use eye navigation" (or the Hands-free profile)
is turned on. It holds:
  - a gaze bar: Recalibrate · Head/Eyes switch · status · Quit hands-free
  - the 2x2 gaze grid, mirroring the step-by-step booking portal (all buttons, no typing)
GazeMode (camera, cursor, preview, big high-contrast style) is attached to this window.
"""

from __future__ import annotations

import time
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from accessshift.ui import gaze_style
from accessshift.ui import theme as theme_mod
from accessshift.ui.gaze_grid import GazeGridPanel
from accessshift.ui.gaze_mode import GazeMode
from accessshift.ui.portal_view import PortalView


class GazeBookingWindow(QWidget):
    exit_requested = Signal()  # Close on the booked popup, eyes closed 5 s, or the window was closed
    problem = Signal(str)  # stopped by a problem: the settings page shows this message

    def __init__(self, repo_root: Path, parent: QWidget | None = None):
        super().__init__(parent, Qt.Window)
        self.setWindowTitle("AccessShift AI  ·  Hands-free booking")
        self.resize(1100, 760)
        self._repo_root = Path(repo_root)
        self._stopping = False

        self.bar = QWidget()
        bar = QHBoxLayout(self.bar)
        bar.setContentsMargins(0, 0, 0, 0)
        self.btn_recalibrate = QPushButton("Recalibrate")
        self.btn_source = QPushButton()
        self.btn_quit = QPushButton("Quit hands-free")
        self.btn_quit.setAccessibleName("Quit hands-free control and go back to AccessShift")
        self.status = QLabel()
        self.status.setWordWrap(True)
        bar.addWidget(self.btn_recalibrate, 1)
        bar.addWidget(self.btn_source, 1)
        bar.addWidget(self.status, 2)
        bar.addWidget(self.btn_quit, 1)  # leave at any time: no booking needed (also: eyes closed 5 s)

        self.portal = self._new_portal()
        self.grid = GazeGridPanel(self.portal)
        layout = QVBoxLayout(self)
        layout.addWidget(self.bar)
        layout.addWidget(self.grid, 1)
        layout.addWidget(self.portal)

        self.gaze = GazeMode(self)
        self.gaze.status.connect(self.status.setText)
        self.gaze.source_changed.connect(self._show_source)
        self.gaze.exit_requested.connect(self.exit_requested)
        self.gaze.problem.connect(self.problem)
        self.btn_recalibrate.clicked.connect(self.gaze.request_recalibrate)
        self.btn_source.clicked.connect(self.gaze.toggle_source)
        self.btn_quit.clicked.connect(self.exit_requested)
        self._show_source(self.gaze.controller.source)
        self.setObjectName("gazeRoot")
        self.apply_theme("standard")

    def apply_theme(self, color_profile: str) -> None:
        """Use the app's colour setting (Standard, High contrast, Warm, Cool)."""
        p = theme_mod.gaze_palette(color_profile)
        styled = gaze_style.is_applied(self)
        if styled:
            gaze_style.restore(self)
        self.setStyleSheet(
            f"QWidget#gazeRoot {{ background: {p.background}; }}"
            f"QLabel {{ color: {p.foreground}; background: transparent; }}"
        )
        self.gaze.palette = p
        self.grid.set_palette(p)
        if styled:
            gaze_style.apply(self, p)

    def apply_settings(self, dwell_ms: int, blink_select: bool) -> None:
        self.gaze.controller.set_dwell_ms(int(dwell_ms))
        self.gaze.controller.blink_select = bool(blink_select)

    def _booking_finished(self, choice: str) -> None:
        if choice == "close":
            self.exit_requested.emit()  # same as leaving hands-free control
            return
        # Start over: the portal is back at step 1; same calibration, new timed booking.
        self.gaze.metrics.start_task(int(time.monotonic() * 1000))
        self.grid.refresh()
        self.status.setText("Starting over. Choose who this visit is for.")

    def _new_portal(self) -> PortalView:
        portal = PortalView(self._repo_root / "assets" / "portal")
        portal.booking_finished.connect(self._booking_finished)
        portal.set_accessible(True)  # the all-buttons, step-by-step booking flow
        portal.hide()  # never shown: the grid mirrors it
        return portal

    def _show_source(self, source: str) -> None:
        other = "Eyes" if source == "head" else "Head"
        self.btn_source.setText(f"Pointing with: {source.capitalize()}\n(switch to {other})")

    # --- lifecycle -----------------------------------------------------------------------
    def start(self) -> None:
        if self.gaze.enabled:
            self.raise_()
            return
        fresh = self._new_portal()  # every session starts at step 1
        self.layout().replaceWidget(self.portal, fresh)
        self.portal.deleteLater()
        self.portal = fresh
        self.grid.set_source(fresh)
        self.show()
        self.raise_()
        self.activateWindow()
        self.gaze.set_enabled(True)
        self.grid.refresh()

    LEAVE_FULL_SCREEN_MS = 900  # macOS animates leaving full screen; hide after it finishes

    def stop(self) -> None:
        self._stopping = True
        try:
            self.gaze.set_enabled(False)
            if self.isFullScreen():
                # Hiding a full-screen window leaves its macOS space behind, empty and black.
                self.showNormal()
                QTimer.singleShot(self.LEAVE_FULL_SCREEN_MS, self._hide_if_stopped)
            else:
                self.hide()
        finally:
            self._stopping = False

    def _hide_if_stopped(self) -> None:
        if not self.gaze.enabled:
            self.hide()

    def recalibrate(self) -> None:
        self.gaze.request_recalibrate()

    def closeEvent(self, event) -> None:
        if not self._stopping and self.gaze.enabled:
            self.exit_requested.emit()  # the control center turns eye navigation off
        self.gaze.set_enabled(False)
        super().closeEvent(event)
