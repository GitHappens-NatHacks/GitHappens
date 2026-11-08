"""2x2 gaze grid: the current portal step's options as giant photo squares.

Mirrors whatever buttons are showing in the source widget (the portal). Choosing a
square clicks the real portal button, then the grid refreshes for the next step.
The portal code itself is untouched.

Layout: 1 option fills the screen, 2 sit side by side, 3 = two on top and one wide
square below, 4 = a 2x2 grid. Confirm (Book + Back) stacks full-height rows so the
final step is not crushed into the lower half of the window.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QRectF, QSize
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QGridLayout, QLabel, QPushButton, QSizePolicy, QVBoxLayout, QWidget

from accessshift.ui import gaze_style

SQUARE_QSS = gaze_style.BUTTON_QSS + "QPushButton { font-size: 28px; }"

# Editorial photos for each booking choice (bundled under assets/ui).
PHOTO_BY_LABEL = {
    'Myself': 'lens-close.jpg',
    'Someone I care for': 'clinic-light.jpg',
    'Check-up': 'pages-light.jpg',
    'Follow-up': 'care-corner.jpg',
    'New concern': 'soft-wall.jpg',
    'Tomorrow 10:00': 'window-seat.jpg',
    'Tomorrow 14:00': 'desk-laptop-a.jpg',
    'Friday 11:30': 'mug-stack.jpg',
    'Book appointment': 'desk-top.jpg',
    'Back': 'cam-bezel.jpg',
}


class PhotoSquare(QPushButton):
    """Large gaze target: photo band on top, label below, soft-blue dwell highlight."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._photo = QPixmap()
        self._tall = False
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def set_photo(self, path: Path | None) -> None:
        if path is None or not path.is_file():
            self._photo = QPixmap()
        else:
            self._photo = QPixmap(str(path))
        self.update()

    def set_tall_layout(self, tall: bool) -> None:
        self._tall = bool(tall)
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        targeted = bool(self.property('gazeTarget'))
        bg = QColor(gaze_style.TARGET_BG if targeted else gaze_style.BUTTON_BG)
        ink = QColor(gaze_style.TEXT)
        border_w = 5 if targeted else 2
        rect = self.rect().adjusted(3, 3, -3, -3)
        p.setPen(QPen(ink, border_w))
        p.setBrush(bg)
        p.drawRoundedRect(rect, 18, 18)

        # Tall confirm cards: photo fills most of the tile; label sits in a clear footer.
        photo_ratio = 0.72 if self._tall else 0.58
        photo_h = int(rect.height() * photo_ratio)
        photo_rect = QRectF(rect.x() + 10, rect.y() + 10, rect.width() - 20, max(48, photo_h))
        if not self._photo.isNull() and photo_rect.height() > 40:
            scaled = self._photo.scaled(
                int(photo_rect.width()),
                int(photo_rect.height()),
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )
            x = int(photo_rect.x() + (photo_rect.width() - scaled.width()) / 2)
            y = int(photo_rect.y() + (photo_rect.height() - scaled.height()) / 2)
            p.setClipRect(photo_rect)
            p.drawPixmap(x, y, scaled)
            p.setClipping(False)
        else:
            p.fillRect(photo_rect, QColor('#E8F0FE'))

        text_top = int(photo_rect.bottom() + 10)
        text_rect = QRectF(rect.x() + 20, text_top, rect.width() - 40, max(48, rect.bottom() - text_top - 14))
        font = QFont('Albert Sans', 26 if self._tall else 22, QFont.Weight.DemiBold)
        p.setFont(font)
        p.setPen(ink)
        p.drawText(text_rect, int(Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap), self.text())
        p.end()


class GazeGridPanel(QWidget):
    def __init__(
        self,
        source: QWidget,
        parent: QWidget | None = None,
        photo_root: Path | None = None,
    ):
        super().__init__(parent)
        self._source = source
        self._photo_root = Path(photo_root) if photo_root else None
        self._targets: list[QPushButton] = []
        self._squares: list[PhotoSquare] = []

        self.setObjectName('gazeGridPanel')
        self.setStyleSheet(
            'QWidget#gazeGridPanel { background: #F5F5F7; }'
            'QLabel#gazeHeroImage { background: #E2EAF4; border: none; }'
            'QLabel#gazeStepHeading { color: #0B1F3A; font-size: 28px; font-weight: 200; }'
        )

        self._hero = QLabel()
        self._hero.setObjectName('gazeHeroImage')
        self._hero.setMinimumHeight(120)
        self._hero.setMaximumHeight(160)
        self._hero.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._hero.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._load_hero('desk-laptop-a.jpg')

        self._heading = QLabel()
        self._heading.setObjectName('gazeStepHeading')
        self._heading.setWordWrap(True)
        self._heading.setMaximumHeight(160)
        self._grid = QGridLayout()
        self._grid.setSpacing(18)
        self._grid.setContentsMargins(4, 4, 4, 4)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 16, 24, 24)
        layout.setSpacing(12)
        layout.addWidget(self._hero)
        layout.addWidget(self._heading)
        layout.addLayout(self._grid, 1)

    def _load_hero(self, filename: str) -> None:
        if self._photo_root is None:
            return
        path = self._photo_root / filename
        if not path.is_file():
            return
        pix = QPixmap(str(path))
        fitted = pix.scaled(
            1400, 180,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self._hero.setPixmap(fitted)

    def _photo_path(self, label: str) -> Path | None:
        if self._photo_root is None:
            return None
        name = PHOTO_BY_LABEL.get(label)
        if not name:
            return None
        path = self._photo_root / name
        return path if path.is_file() else None

    def heading(self) -> str:
        return self._heading.text()

    def grid_layout(self) -> QGridLayout:
        return self._grid

    def visible_squares(self) -> list[QPushButton]:
        return self._squares[: len(self._targets)]

    def _visible_in_source(self, kind):
        return [w for w in self._source.findChildren(kind) if w.isVisibleTo(self._source)]

    def refresh(self) -> None:
        self._targets = [b for b in self._visible_in_source(QPushButton) if b.isEnabled()]
        texts = [lbl.text() for lbl in self._visible_in_source(QLabel) if lbl.text().strip()]
        is_confirm = any(t.text() == 'Book appointment' for t in self._targets)

        if is_confirm:
            # Keep title + booking summary; drop the long hint so options get the height.
            keep = []
            for t in texts:
                if t.startswith('If something'):
                    continue
                keep.append(t)
            self._heading.setText('\n'.join(keep[:5]))
            self._heading.setMaximumHeight(110)
            self._hero.hide()
        else:
            self._heading.setText('\n'.join(texts))
            self._heading.setMaximumHeight(160)
            self._hero.show()
            step_heroes = ('desk-laptop-a.jpg', 'clinic-light.jpg', 'window-seat.jpg', 'care-corner.jpg')
            if self._photo_root is not None:
                self._load_hero(step_heroes[min(max(len(self._targets) - 1, 0), len(step_heroes) - 1)])

        while len(self._squares) < len(self._targets):
            self._squares.append(self._make_square(len(self._squares)))
        for square in self._squares:
            self._grid.removeWidget(square)
            square.hide()

        n = len(self._targets)
        stack_confirm = is_confirm and n == 2
        for i, (square, target) in enumerate(zip(self._squares, self._targets)):
            label = target.text()
            square.setText(label)
            square.set_photo(self._photo_path(label))
            square.set_tall_layout(stack_confirm)
            if stack_confirm:
                # Full-width stacked Book / Back so the final step fills the window.
                self._grid.addWidget(square, i, 0, 1, 2)
                square.setMinimumHeight(220)
            else:
                row, col = divmod(i, 2)
                span = 2 if (i == n - 1 and n % 2 == 1 and n > 1) else 1
                if n == 1:
                    span = 2
                self._grid.addWidget(square, row, col, 1, span)
                square.setMinimumHeight(gaze_style.BUTTON_HEIGHT)
            square.show()

        rows_used = n if stack_confirm else (n + 1) // 2
        for r in range(max(self._grid.rowCount(), rows_used)):
            self._grid.setRowStretch(r, 1 if r < rows_used else 0)
        for c in range(2):
            self._grid.setColumnStretch(c, 1)

    def _make_square(self, index: int) -> PhotoSquare:
        square = PhotoSquare()
        square.setStyleSheet(SQUARE_QSS)
        square.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        square.setMinimumHeight(gaze_style.BUTTON_HEIGHT)
        square.setMinimumSize(QSize(220, 200))
        square.clicked.connect(lambda _=False, i=index: self._choose(i))
        return square

    def _choose(self, index: int) -> None:
        if index < len(self._targets):
            self._targets[index].click()
        self.refresh()

    def showEvent(self, event) -> None:
        self.refresh()
        super().showEvent(event)
