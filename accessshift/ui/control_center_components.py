"""Small reusable PySide6 controls for AccessShift's cross-platform UI."""
from __future__ import annotations

from PySide6.QtCore import Qt, QSize, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (
    QAbstractButton, QFrame, QHBoxLayout, QLabel, QPushButton,
    QSizePolicy, QVBoxLayout, QWidget,
)


class Switch(QAbstractButton):
    """Accessible, keyboard-operable toggle with the standard toggled(bool) signal."""

    def __init__(self, label: str = "", parent: QWidget | None = None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(48, 27)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAccessibleName(label)
        self.setToolTip(label)

    def sizeHint(self) -> QSize:
        return QSize(48, 27)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        active = self.isChecked()
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor('#674BE8' if active else '#D6DCEA'))
        painter.drawRoundedRect(1, 2, 46, 23, 11.5, 11.5)
        painter.setBrush(QColor('#FFFFFF'))
        painter.drawEllipse(25 if active else 4, 5, 18, 18)
        if self.hasFocus():
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(QColor('#8E79EF'), 2))
            painter.drawRoundedRect(0, 1, 47, 25, 12, 12)


def label(text: str, name: str = 'bodyText', wrap: bool = False) -> QLabel:
    item = QLabel(text)
    item.setObjectName(name)
    item.setWordWrap(wrap)
    return item


def button(text: str, variant: str = 'secondaryButton') -> QPushButton:
    widget = QPushButton(text)
    widget.setObjectName(variant)
    widget.setCursor(Qt.CursorShape.PointingHandCursor)
    widget.setMinimumHeight(42)
    return widget


def card(*, name: str = 'card', margins: int = 20, spacing: int = 12) -> tuple[QFrame, QVBoxLayout]:
    box = QFrame()
    box.setObjectName(name)
    layout = QVBoxLayout(box)
    layout.setContentsMargins(margins, margins, margins, margins)
    layout.setSpacing(spacing)
    return box, layout


class PreferenceRow(QFrame):
    """One option, with explanatory copy and a reusable toggle."""
    changed = Signal(bool)

    def __init__(self, heading: str, details: str, *, checked: bool = False):
        super().__init__()
        self.setObjectName('card')
        lay = QHBoxLayout(self)
        lay.setContentsMargins(19, 16, 19, 16)
        lay.setSpacing(20)
        texts = QVBoxLayout()
        texts.setSpacing(6)
        title = label(heading, 'cardTitle')
        desc = label(details, 'bodyText', True)
        desc.setMaximumWidth(540)
        texts.addWidget(title)
        texts.addWidget(desc)
        lay.addLayout(texts, 1)
        self.switch = Switch(heading)
        self.switch.setChecked(checked)
        self.switch.toggled.connect(self.changed.emit)
        lay.addWidget(self.switch, alignment=Qt.AlignmentFlag.AlignVCenter)

    def set_value(self, value: bool) -> None:
        self.switch.blockSignals(True)
        self.switch.setChecked(value)
        self.switch.blockSignals(False)


class StatCard(QFrame):
    def __init__(self, heading: str, value: str, description: str):
        super().__init__()
        self.setObjectName('card')
        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 16, 18, 16)
        lay.setSpacing(8)
        lay.addWidget(label(heading, 'subtle'))
        self.value = label(value, 'number')
        lay.addWidget(self.value)
        lay.addWidget(label(description, 'micro', True))
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
