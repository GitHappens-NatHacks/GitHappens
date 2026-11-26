"""2x2 gaze grid: the current portal step's options as giant squares.

Mirrors whatever buttons are showing in the source widget (the portal). Choosing a
square clicks the real portal button, then the grid refreshes for the next step.
The portal code itself is untouched.

Layout: 1 option fills the screen, 2 sit side by side, 3 = two on top and one wide
square below, 4 = a 2x2 grid (more options keep filling rows of two).
"""

from __future__ import annotations

from PySide6.QtWidgets import QGridLayout, QLabel, QPushButton, QSizePolicy, QVBoxLayout, QWidget

from accessshift.ui import gaze_style

SQUARE_FONT_PX = 30


class GazeGridPanel(QWidget):
    def __init__(self, source: QWidget, parent: QWidget | None = None):
        super().__init__(parent)
        self._source = source
        self._targets: list[QPushButton] = []  # portal buttons behind the visible squares
        self._squares: list[QPushButton] = []  # reused, so a clicked square is never deleted mid-click
        self._palette = None  # app colour palette (None = high-contrast default)

        self._heading = QLabel()
        self._heading.setWordWrap(True)
        self._heading.setStyleSheet("font-size: 26px; font-weight: 700;")
        self._grid = QGridLayout()
        self._grid.setSpacing(16)

        layout = QVBoxLayout(self)
        layout.addWidget(self._heading)
        layout.addLayout(self._grid, 1)

    def set_palette(self, palette) -> None:
        self._palette = palette
        qss = gaze_style.button_qss(palette, SQUARE_FONT_PX)
        for square in self._squares:
            square.setStyleSheet(qss)
        fg = palette.foreground if palette is not None else gaze_style.TEXT
        self._heading.setStyleSheet(f"font-size: 26px; font-weight: 700; color: {fg};")

    def set_source(self, source: QWidget) -> None:
        self._source = source
        self.refresh()

    # --- read back -------------------------------------------------------------------
    def heading(self) -> str:
        return self._heading.text()

    def grid_layout(self) -> QGridLayout:
        return self._grid

    def visible_squares(self) -> list[QPushButton]:
        return self._squares[: len(self._targets)]

    # --- mirror the source --------------------------------------------------------------
    def _visible_in_source(self, kind):
        return [w for w in self._source.findChildren(kind) if w.isVisibleTo(self._source)]

    def refresh(self) -> None:
        self._targets = [b for b in self._visible_in_source(QPushButton) if b.isEnabled()]
        texts = [lbl.text() for lbl in self._visible_in_source(QLabel) if lbl.text().strip()]
        self._heading.setText("\n".join(texts))

        while len(self._squares) < len(self._targets):
            self._squares.append(self._make_square(len(self._squares)))
        for square in self._squares:
            self._grid.removeWidget(square)
            square.hide()

        n = len(self._targets)
        for i, (square, target) in enumerate(zip(self._squares, self._targets)):
            square.setText(target.text())
            row, col = divmod(i, 2)
            span = 2 if (i == n - 1 and n % 2 == 1 and n > 1) else 1
            if n == 1:
                span = 2
            self._grid.addWidget(square, row, col, 1, span)
            square.show()
        for r in range(self._grid.rowCount()):
            self._grid.setRowStretch(r, 1 if r < (n + 1) // 2 else 0)
        for c in range(2):
            self._grid.setColumnStretch(c, 1)

    def _make_square(self, index: int) -> QPushButton:
        square = QPushButton()
        square.setProperty(gaze_style.OWN_STYLE, True)
        square.setStyleSheet(gaze_style.button_qss(self._palette, SQUARE_FONT_PX))
        square.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        square.setMinimumHeight(gaze_style.BUTTON_HEIGHT)
        square.clicked.connect(lambda _=False, i=index: self._choose(i))
        return square

    def _choose(self, index: int) -> None:
        if index < len(self._targets):
            self._targets[index].click()
        self.refresh()

    def showEvent(self, event) -> None:
        self.refresh()
        super().showEvent(event)
