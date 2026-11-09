"""Line icons for Younify, drawn with QPainter in one consistent stroke.

Every icon is authored on a 24 x 24 grid with a 1.8 px round stroke, so icons look
like one family at any size and take their colour from the active theme.
"""
from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import QLabel, QWidget


def _draw(p: QPainter, name: str) -> None:  # noqa: C901 - one small drawing per icon
    path = QPainterPath()
    if name == 'home':
        path.moveTo(3.5, 11)
        path.lineTo(12, 4)
        path.lineTo(20.5, 11)
        path.moveTo(6, 9.5)
        path.lineTo(6, 20)
        path.lineTo(18, 20)
        path.lineTo(18, 9.5)
        path.moveTo(10, 20)
        path.lineTo(10, 14.5)
        path.lineTo(14, 14.5)
        path.lineTo(14, 20)
    elif name == 'dashboard':
        for x, y, w, h in ((4, 4, 7, 9), (13, 4, 7, 5), (13, 11, 7, 9), (4, 15, 7, 5)):
            path.addRoundedRect(QRectF(x, y, w, h), 1.8, 1.8)
    elif name == 'profile':
        path.addEllipse(QPointF(12, 8.5), 3.8, 3.8)
        path.moveTo(4.5, 20)
        path.cubicTo(5.5, 15.5, 8.5, 14, 12, 14)
        path.cubicTo(15.5, 14, 18.5, 15.5, 19.5, 20)
    elif name == 'head':
        path.addEllipse(QPointF(12, 10), 5, 5.5)
        path.moveTo(9.5, 15)
        path.lineTo(9.5, 20)
        path.moveTo(14.5, 15)
        path.lineTo(14.5, 20)
        path.moveTo(3, 10)
        path.lineTo(5, 8)
        path.moveTo(3, 10)
        path.lineTo(5, 12)
        path.moveTo(21, 10)
        path.lineTo(19, 8)
        path.moveTo(21, 10)
        path.lineTo(19, 12)
    elif name == 'eye':
        path.moveTo(2.5, 12)
        path.quadTo(12, 3, 21.5, 12)
        path.quadTo(12, 21, 2.5, 12)
        path.addEllipse(QPointF(12, 12), 3.2, 3.2)
    elif name == 'steady':
        path.addEllipse(QPointF(12, 12), 7.5, 7.5)
        path.addEllipse(QPointF(12, 12), 2.6, 2.6)
        for a, b in (((12, 2), (12, 5.5)), ((12, 18.5), (12, 22)), ((2, 12), (5.5, 12)), ((18.5, 12), (22, 12))):
            path.moveTo(*a)
            path.lineTo(*b)
    elif name == 'interface':
        for y, knob in ((6, 15), (12, 8), (18, 13)):
            path.moveTo(4, y)
            path.lineTo(20, y)
            path.addEllipse(QPointF(knob, y), 2.2, 2.2)
    elif name == 'lab':
        path.moveTo(9.5, 3.5)
        path.lineTo(14.5, 3.5)
        path.moveTo(10.5, 3.5)
        path.lineTo(10.5, 9.5)
        path.lineTo(5, 18.5)
        path.quadTo(4.2, 20.5, 6.5, 20.5)
        path.lineTo(17.5, 20.5)
        path.quadTo(19.8, 20.5, 19, 18.5)
        path.lineTo(13.5, 9.5)
        path.lineTo(13.5, 3.5)
        path.moveTo(7.5, 15)
        path.lineTo(16.5, 15)
    elif name == 'tint':
        path.moveTo(12, 3.5)
        path.cubicTo(8, 9, 6, 11.5, 6, 14.5)
        path.cubicTo(6, 18, 8.8, 20.5, 12, 20.5)
        path.cubicTo(15.2, 20.5, 18, 18, 18, 14.5)
        path.cubicTo(18, 11.5, 16, 9, 12, 3.5)
    elif name == 'text':
        path.moveTo(4, 6)
        path.lineTo(4, 4.5)
        path.lineTo(14, 4.5)
        path.lineTo(14, 6)
        path.moveTo(9, 4.5)
        path.lineTo(9, 19.5)
        path.moveTo(7, 19.5)
        path.lineTo(11, 19.5)
        path.moveTo(14.5, 11)
        path.lineTo(20, 11)
        path.moveTo(17.25, 11)
        path.lineTo(17.25, 19.5)
    elif name == 'highlight':
        path.addRoundedRect(QRectF(3.5, 9, 17, 7), 2, 2)
        path.moveTo(3.5, 19.5)
        path.lineTo(20.5, 19.5)
        path.moveTo(7, 4.5)
        path.lineTo(17, 4.5)
    elif name == 'arrow':
        path.moveTo(5, 12)
        path.lineTo(19, 12)
        path.moveTo(13.5, 6.5)
        path.lineTo(19, 12)
        path.lineTo(13.5, 17.5)
    elif name == 'back':
        path.moveTo(19, 12)
        path.lineTo(5, 12)
        path.moveTo(10.5, 6.5)
        path.lineTo(5, 12)
        path.lineTo(10.5, 17.5)
    elif name == 'check':
        path.moveTo(5, 12.5)
        path.lineTo(10, 17.5)
        path.lineTo(19, 7)
    elif name == 'play':
        path.moveTo(8, 5)
        path.lineTo(19, 12)
        path.lineTo(8, 19)
        path.closeSubpath()
    elif name == 'external':
        path.moveTo(13, 4.5)
        path.lineTo(19.5, 4.5)
        path.lineTo(19.5, 11)
        path.moveTo(19.5, 4.5)
        path.lineTo(11, 13)
        path.moveTo(17, 14)
        path.lineTo(17, 19.5)
        path.lineTo(4.5, 19.5)
        path.lineTo(4.5, 7)
        path.lineTo(10, 7)
    elif name == 'blink':
        path.moveTo(3, 11)
        path.quadTo(12, 18.5, 21, 11)
        for a, b in (((6, 14.5), (4.5, 17)), ((12, 16.5), (12, 19.5)), ((18, 14.5), (19.5, 17))):
            path.moveTo(*a)
            path.lineTo(*b)
    p.drawPath(path)


def pixmap(name: str, color: str, size: int = 22) -> QPixmap:
    ratio = 2.0
    pm = QPixmap(QSize(round(size * ratio), round(size * ratio)))
    pm.setDevicePixelRatio(ratio)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.scale(size / 24.0, size / 24.0)
    pen = QPen(QColor(color), 1.8)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.BrushStyle.NoBrush)
    _draw(p, name)
    p.end()
    return pm


def icon(name: str, color: str, size: int = 22) -> QIcon:
    return QIcon(pixmap(name, color, size))


class IconTile(QLabel):
    """An icon on a rounded, softly coloured tile (theme aware via set_colors)."""

    def __init__(self, name: str, size: int = 44, parent: QWidget | None = None):
        super().__init__(parent)
        self._name = name
        self._size = size
        self.setFixedSize(size, size)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setAccessibleName('')
        self.set_colors('#E5F2EF', '#176F6C')

    def set_colors(self, background: str, foreground: str) -> None:
        radius = round(self._size * 0.3)
        self.setStyleSheet(f'background: {background}; border-radius: {radius}px;')
        self.setPixmap(pixmap(self._name, foreground, round(self._size * 0.52)))
