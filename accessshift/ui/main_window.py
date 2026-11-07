"""AccessShift control center + a separate, live-updating healthcare preview.

The control center stays open. One modeless window holds the ORIGINAL local
healthcare form, and reacts to preference changes emitted by control_center.py.
No browser extensions or third-party website adaptation are used.
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel
from accessshift.ui.control_center import MainWindow as ControlCenterWindow
from accessshift.ui.control_center_components import button, card, label
from accessshift.ui.healthcare_demo_window import HealthcareDemoWindow


class MainWindow(ControlCenterWindow):
    def __init__(self, repo_root: Path):
        super().__init__(repo_root=repo_root)
        self._healthcare_demo: HealthcareDemoWindow | None = None
        self._add_local_demo_entries()
        self._add_demo_toolbar_button()
        # Existing control center signal: emitted on every setting edit.
        # Use it instead of reading a file on a timer or polling the UI.
        self.preferences_changed.connect(self._update_live_demo)

    def _add_demo_toolbar_button(self) -> None:
        shortcut = button('Open Demo Lab  ↗', 'secondaryButton')
        shortcut.setToolTip('Open the separate, local healthcare demo window')
        shortcut.setMinimumHeight(36)
        shortcut.clicked.connect(self._open_healthcare_demo)
        self.top_bar_layout.insertWidget(self.top_bar_layout.count() - 1, shortcut)

    def _add_local_demo_entries(self) -> None:
        # Retain the Demo Lab launcher in its own testing tab.
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

        # Shortcut from the actual preferences page, so the first window can
        # remain on the settings controls while the second stays open.
        preferences_page = self._pages['interface']
        # The SmartInterface page is the live control panel for the preview.
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
        # Insert immediately before the preferences option cards.
        pref_layout.insertWidget(4, preview_card)

    def _open_healthcare_demo(self) -> None:
        # Focus the SmartInterface settings in the FIRST window.
        self._navigate('interface')
        if self._healthcare_demo is None:
            self._healthcare_demo = HealthcareDemoWindow(
                self.repo_root, smart_interface_enabled=False, parent=self)
            # Explicitly register this one extra AccessShift-owned window; never monitors.
            self.tint_manager.register_window(self._healthcare_demo)
        # Always begin at the original baseline to make the comparison obvious.
        # The first manual preference change enables the live adaptation.
        self._healthcare_demo.enter_baseline()
        self._healthcare_demo.show()
        self._healthcare_demo.raise_()
        self._healthcare_demo.activateWindow()

    def _update_live_demo(self, settings: object) -> None:
        if self._healthcare_demo is not None and self._healthcare_demo.isVisible():
            # No replacement of fields, no reload, no network operations.
            self._healthcare_demo.apply_preferences(dict(settings))


__all__ = ['MainWindow']
