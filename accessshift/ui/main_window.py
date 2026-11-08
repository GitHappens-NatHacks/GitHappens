"""AccessShift entry window: paper Control Center with GazeControl focus mode.

The Control Center (settings, SteadyHand lab, SmartInterface, speech) is the
default shell. Enabling gaze_control hides the top chrome and opens the hands-free
booking layout with head/eye pointing.
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from accessshift.ui.control_center import MainWindow as ControlCenterWindow
from accessshift.ui.control_center_components import button, card, label
from accessshift.ui.gaze_grid import GazeGridPanel
from accessshift.ui.gaze_mode import GazeMode
from accessshift.ui.healthcare_demo_window import HealthcareDemoWindow
from accessshift.ui.portal_view import PortalView


class MainWindow(ControlCenterWindow):
    def __init__(self, repo_root: Path):
        super().__init__(repo_root=repo_root)
        self._healthcare_demo: HealthcareDemoWindow | None = None
        self._build_gaze_focus()
        self._wire_gaze()
        self._add_local_demo_entries()
        self._add_demo_toolbar_button()
        self.preferences_changed.connect(self._update_live_demo)
        self.engine.modules_changed.connect(self._sync_gaze_from_engine)
        self._sync_gaze_from_engine(self.engine.modules)

    # --- healthcare demo (Elizabeth) -------------------------------------------------
    def _add_demo_toolbar_button(self) -> None:
        shortcut = button('Open Demo Lab', 'secondaryButton')
        shortcut.setToolTip('Open the separate, local healthcare demo window')
        shortcut.setMinimumHeight(36)
        shortcut.clicked.connect(self._open_healthcare_demo)
        self.top_bar_layout.insertWidget(self.top_bar_layout.count() - 1, shortcut)

    def _add_local_demo_entries(self) -> None:
        test_page = self._pages['test']
        test_layout = test_page.widget().layout()
        demo, column = card(name='innerCard', margins=19, spacing=10)
        column.addWidget(label('Healthcare Demo Lab · live SmartInterface', 'sectionTitle'))
        column.addWidget(label(
            'Open a separate fictional healthcare form. AccessShift stays open on SmartInterface settings: '
            'change a slider or theme and watch the same form update instantly.',
            'bodyText', True))
        launch = button('Launch healthcare preview  ↗', 'primaryButton')
        launch.setAccessibleName('Open live local healthcare form preview')
        launch.clicked.connect(self._open_healthcare_demo)
        column.addWidget(launch, alignment=Qt.AlignmentFlag.AlignLeft)
        test_layout.insertWidget(4, demo)

        preferences_page = self._pages['interface']
        pref_layout = preferences_page.widget().layout()
        preview_card, pl = card(name='innerCard', margins=18, spacing=9)
        pl.addWidget(label('Live healthcare preview', 'sectionTitle'))
        pl.addWidget(label(
            'Keep this window open alongside a fictional appointment form. Changes to text size, colour, '
            'tint, layout and target size apply immediately without resetting entered data.',
            'bodyText', True))
        open_button = button('Open separate demo window  ↗', 'secondaryButton')
        open_button.clicked.connect(self._open_healthcare_demo)
        pl.addWidget(open_button, alignment=Qt.AlignmentFlag.AlignLeft)
        pref_layout.insertWidget(4, preview_card)

    def _open_healthcare_demo(self) -> None:
        self._navigate('interface')
        if self._healthcare_demo is None:
            self._healthcare_demo = HealthcareDemoWindow(
                self.repo_root, smart_interface_enabled=False, parent=self)
            self.tint_manager.register_window(self._healthcare_demo)
        self._healthcare_demo.enter_baseline()
        self._healthcare_demo.show()
        self._healthcare_demo.raise_()
        self._healthcare_demo.activateWindow()

    def _update_live_demo(self, settings: object) -> None:
        if self._healthcare_demo is not None and self._healthcare_demo.isVisible():
            self._healthcare_demo.apply_preferences(dict(settings))

    # --- GazeControl focus mode ------------------------------------------------------
    def _build_gaze_focus(self) -> None:
        """Booking portal + 2x2 grid used while gaze/head pointing is on."""
        root_layout = self.centralWidget().layout()

        self.chk_gaze = QCheckBox('GazeControl')
        self.chk_gaze.hide()  # driven by Control Center toggle / engine profiles

        chrome_qss = (
            'QPushButton {'
            '  color: #0B1F3A; background: #FFFFFF; border: 1px solid #B8C9DE;'
            '  border-radius: 980px; padding: 14px 18px; font-size: 15px; font-weight: 650;'
            '}'
            'QPushButton:hover { background: #E8F0FE; border-color: #2F6FED; }'
        )
        exit_qss = (
            'QPushButton {'
            '  color: #FFFFFF; background: #0B1F3A; border: none;'
            '  border-radius: 18px; padding: 16px 20px; font-size: 16px; font-weight: 650;'
            '}'
            'QPushButton:hover { background: #123A6D; }'
        )

        self.gaze_bar = QWidget()
        self.gaze_bar.setObjectName('gazeFocusBar')
        bar = QHBoxLayout(self.gaze_bar)
        bar.setContentsMargins(28, 16, 28, 16)
        bar.setSpacing(14)
        self.btn_recalibrate_gaze = QPushButton('Recalibrate gaze')
        self.btn_gaze_source = QPushButton()
        self.gaze_status = QLabel()
        self.gaze_status.setObjectName('gazeStatusLabel')
        self.gaze_status.setWordWrap(True)
        self.btn_exit_gaze = QPushButton('Exit gaze control\n(or close your eyes for 3 s)')
        self.btn_exit_gaze.setMinimumHeight(96)
        self.btn_exit_gaze.clicked.connect(lambda: self.chk_gaze.setChecked(False))
        for btn in (self.btn_recalibrate_gaze, self.btn_gaze_source):
            btn.setProperty('gazeChrome', True)
            btn.setMinimumHeight(52)
            btn.setStyleSheet(chrome_qss)
        self.btn_exit_gaze.setProperty('gazeChrome', True)
        self.btn_exit_gaze.setStyleSheet(exit_qss)
        bar.addWidget(self.btn_recalibrate_gaze, 1)
        bar.addWidget(self.btn_gaze_source, 1)
        bar.addWidget(self.gaze_status, 1)
        bar.addWidget(self.btn_exit_gaze, 2)
        self.gaze_bar.hide()

        self.portal = PortalView(self.repo_root / 'assets' / 'portal')
        self.gaze_grid = GazeGridPanel(
            self.portal,
            photo_root=self.repo_root / 'assets' / 'ui',
        )
        self.gaze_grid.hide()

        self._focus_host = QWidget()
        self._focus_host.setObjectName('gazeFocusRoot')
        self._focus_host.setStyleSheet(
            'QWidget#gazeFocusRoot { background: #F5F5F7; }'
            'QWidget#gazeFocusBar { background: #FFFFFF; border-bottom: 1px solid #D7E0EC; }'
            'QLabel#gazeStatusLabel { color: #3E5370; font-size: 15px; font-weight: 500; padding: 0 8px; }'
        )
        focus = QVBoxLayout(self._focus_host)
        focus.setContentsMargins(0, 0, 0, 0)
        focus.setSpacing(0)
        focus.addWidget(self.gaze_bar)
        focus.addWidget(self.portal, 1)
        focus.addWidget(self.gaze_grid, 1)
        self._focus_host.hide()
        root_layout.addWidget(self._focus_host, 3)

    def _wire_gaze(self) -> None:
        self.gaze = GazeMode(self)
        self.gaze.status.connect(self.gaze_status.setText)
        self.gaze.status.connect(self._on_gaze_status)
        self.gaze.exit_requested.connect(lambda: self.chk_gaze.setChecked(False))
        self.gaze.source_changed.connect(self._show_gaze_source)
        self.btn_recalibrate_gaze.clicked.connect(self.gaze.request_recalibrate)
        self.btn_gaze_source.clicked.connect(self.gaze.toggle_source)
        self.chk_gaze.toggled.connect(self._on_chk_gaze_toggled)
        self._show_gaze_source(self.gaze.controller.source)

    def _on_gaze_status(self, text: str) -> None:
        self.footer_status.setText(text)

    def _show_gaze_source(self, source: str) -> None:
        other = 'Eyes' if source == 'head' else 'Head'
        self.btn_gaze_source.setText(
            f'Pointing with: {source.capitalize()}\n(switch to {other})'
        )

    def _on_chk_gaze_toggled(self, enabled: bool) -> None:
        self.engine.set_module('gaze_control', enabled)
        self.prefs.gaze_control = enabled
        if enabled:
            self.prefs.profile = 'custom' if self.prefs.profile == 'parkinsons' else self.prefs.profile
        self._apply_gaze_focus(enabled)
        self._save()
        self._refresh()

    def _sync_gaze_from_engine(self, modules) -> None:
        enabled = bool(modules.gaze_control)
        if self.chk_gaze.isChecked() != enabled:
            self.chk_gaze.blockSignals(True)
            self.chk_gaze.setChecked(enabled)
            self.chk_gaze.blockSignals(False)
        self._apply_gaze_focus(enabled)

    def _apply_gaze_focus(self, enabled: bool) -> None:
        self.sidebar.setVisible(not enabled)
        self.workspace.setVisible(not enabled)
        self._focus_host.setVisible(enabled)
        self.gaze_bar.setVisible(enabled)
        if enabled:
            self.portal.set_accessible(True)
            self.portal.setVisible(False)
            self.gaze_grid.setVisible(True)
        else:
            self.portal.set_accessible(False)
            self.portal.setVisible(True)
            self.gaze_grid.setVisible(False)
        self.gaze.set_enabled(enabled)
        # Exit button stays wide enough for dwell / blink hits.
        if enabled and self.gaze_bar.width() > 0:
            self.btn_exit_gaze.setMinimumWidth(int(0.35 * self.gaze_bar.width()))

    def _request_calibration(self) -> None:
        if not self.gaze.enabled:
            self.chk_gaze.setChecked(True)
        if not self.gaze.enabled:
            QMessageBox.warning(
                self,
                'Gaze calibration',
                'Could not start the camera. Check Camera privacy settings, then try again.',
            )
            return
        self.gaze.request_recalibrate()

    def _change_module(self, key, value) -> None:
        super()._change_module(key, value)
        if key == 'gaze_control':
            if self.chk_gaze.isChecked() != bool(value):
                self.chk_gaze.setChecked(bool(value))

    def closeEvent(self, event) -> None:
        self.gaze.set_enabled(False)
        super().closeEvent(event)
