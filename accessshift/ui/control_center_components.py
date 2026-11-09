"""Small reusable PySide6 controls for Younify's cross-platform UI."""
from __future__ import annotations

from PySide6.QtCore import QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (
    QAbstractButton, QFrame, QHBoxLayout, QLabel, QPushButton,
    QSizePolicy, QVBoxLayout, QWidget,
)


class Switch(QAbstractButton):
    """Accessible, keyboard-operable toggle with the standard toggled(bool) signal."""

    # Shared colours, updated with the colour theme (see Switch.set_colors).
    ON = '#3478D4'
    OFF = '#B9C7C2'
    KNOB = '#FFFFFF'
    FOCUS = '#176F6C'

    def __init__(self, label: str = "", parent: QWidget | None = None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(52, 30)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAccessibleName(label)
        self.setToolTip(label)

    @classmethod
    def set_colors(cls, on: str, off: str, knob: str, focus: str) -> None:
        cls.ON, cls.OFF, cls.KNOB, cls.FOCUS = on, off, knob, focus

    def sizeHint(self) -> QSize:
        return QSize(52, 30)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        active = self.isChecked()
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(self.ON if active else self.OFF))
        painter.drawRoundedRect(QRectF(2, 3, 48, 24), 12, 12)
        painter.setBrush(QColor(self.KNOB))
        painter.drawEllipse(QRectF(28 if active else 6, 7, 16, 16))
        if self.hasFocus():
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(QColor(self.FOCUS), 2))
            painter.drawRoundedRect(QRectF(1, 1, 50, 28), 14, 14)


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


def divider() -> QFrame:
    line = QFrame()
    line.setObjectName('divider')
    return line


class PreferenceRow(QFrame):
    """One option: a bold heading, a quieter description and a toggle. The whole row is clickable."""
    changed = Signal(bool)

    def __init__(self, heading: str, details: str, *, checked: bool = False, framed: bool = True):
        super().__init__()
        self.setObjectName('card' if framed else 'plainRow')
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(20, 16, 18, 16) if framed else lay.setContentsMargins(0, 8, 0, 8)
        lay.setSpacing(20)
        texts = QVBoxLayout()
        texts.setSpacing(4)
        self.title = label(heading, 'cardTitle')
        self.desc = label(details, 'bodyText', True)
        texts.addWidget(self.title)
        texts.addWidget(self.desc)
        lay.addLayout(texts, 1)
        self.switch = Switch(heading)
        self.switch.setChecked(checked)
        self.switch.toggled.connect(self.changed.emit)
        lay.addWidget(self.switch, alignment=Qt.AlignmentFlag.AlignVCenter)

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self.rect().contains(event.position().toPoint()):
            self.switch.toggle()
        super().mouseReleaseEvent(event)

    def set_value(self, value: bool) -> None:
        self.switch.blockSignals(True)
        self.switch.setChecked(value)
        self.switch.blockSignals(False)
        self.switch.update()


class ChoiceCard(QPushButton):
    """A large, checkable card with a distinct heading, description and optional chips."""

    def __init__(self, title: str, description: str, chips: tuple[str, ...] = (), icon_widget: QWidget | None = None):
        super().__init__()
        self.setObjectName('choiceCard')
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAccessibleName(title)
        self.setAccessibleDescription(description)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 18, 20, 18)
        lay.setSpacing(8)
        top = QHBoxLayout()
        top.setSpacing(12)
        if icon_widget is not None:
            top.addWidget(icon_widget, 0, Qt.AlignmentFlag.AlignTop)
        heading = QVBoxLayout()
        heading.setSpacing(4)
        self.title = label(title, 'choiceTitle', True)
        self.desc = label(description, 'choiceDesc', True)
        heading.addWidget(self.title)
        heading.addWidget(self.desc)
        top.addLayout(heading, 1)
        self.check = label('Selected', 'choiceCheck')
        self.check.setVisible(False)
        top.addWidget(self.check, 0, Qt.AlignmentFlag.AlignTop)
        lay.addLayout(top)
        if chips:
            row = QHBoxLayout()
            row.setSpacing(6)
            for text in chips:
                row.addWidget(label(text, 'chip'))
            row.addStretch(1)
            lay.addLayout(row)
        for child in self.findChildren(QLabel):
            child.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.toggled.connect(self.check.setVisible)

    def sizeHint(self) -> QSize:
        return self.layout().sizeHint()

    def minimumSizeHint(self) -> QSize:
        return self.layout().minimumSize()


class SwatchButton(QPushButton):
    """A checkable colour sample: paints its colours plus a caption, so the choice is visible, not described."""

    def __init__(self, caption: str, colors: tuple[str, ...], text_color: str = '#252B29'):
        super().__init__()
        self.setObjectName('swatchButton')
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAccessibleName(caption)
        self.setToolTip(caption)
        self.setMinimumSize(120, 84)
        self.caption = caption
        self.colors = colors
        self.text_color = text_color

    def set_caption_color(self, color: str) -> None:
        self.text_color = color
        self.update()

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        area = QRectF(self.rect()).adjusted(10, 10, -10, -32)
        n = max(1, len(self.colors))
        width = area.width() / n
        for i, color in enumerate(self.colors):
            p.setPen(QPen(QColor(0, 0, 0, 40), 1))
            p.setBrush(QColor(color))
            p.drawRoundedRect(QRectF(area.x() + i * width, area.y(), width - (4 if i < n - 1 else 0), area.height()), 6, 6)
        p.setPen(QColor(self.text_color))
        font = p.font()
        font.setBold(True)
        font.setPixelSize(13)
        p.setFont(font)
        p.drawText(QRectF(self.rect()).adjusted(8, 0, -8, -9), Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignBottom,
                   self.caption)
        p.end()
