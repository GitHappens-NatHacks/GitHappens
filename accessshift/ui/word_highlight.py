"""Optional word highlighting: a reading focus aid (helpful for many people with ADHD).

When it is on, the word under the pointer gets a soft marker-pen highlight in every
AccessShift window, so it is easier to keep your place while reading. It only paints
a transparent layer on top of AccessShift's own windows: text is never changed and
clicks always pass straight through.
"""
from __future__ import annotations

from PySide6.QtCore import QObject, QPointF, QRect, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QCursor, QFontMetricsF, QPainter, QTextLayout, QTextLine, QTextOption
from PySide6.QtWidgets import QApplication, QLabel, QWidget

POLL_MS = 60


def _might_be_rich(text: str) -> bool:
    try:
        from PySide6.QtGui import Qt as GuiQt
        return bool(GuiQt.mightBeRichText(text))
    except AttributeError:
        return '<' in text and '>' in text


class _HighlightLayer(QWidget):
    """Window-sized, mouse-transparent layer that paints one highlight rectangle."""

    def __init__(self, window: QWidget):
        super().__init__(window)
        self.setObjectName('accessshiftWordHighlight')
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.rect_f = QRectF()
        self.color = QColor('#FFE07A')
        self.setGeometry(window.rect())

    def show_rect(self, rect: QRectF, color: str) -> None:
        old = self.rect_f.toAlignedRect().adjusted(-3, -3, 3, 3)
        self.rect_f = rect
        self.color = QColor(color)
        if self.geometry() != self.parentWidget().rect():
            self.setGeometry(self.parentWidget().rect())
        self.raise_()
        self.show()
        self.update(old)
        self.update(rect.toAlignedRect().adjusted(-3, -3, 3, 3))

    def clear(self) -> None:
        if not self.rect_f.isNull():
            old = self.rect_f.toAlignedRect().adjusted(-3, -3, 3, 3)
            self.rect_f = QRectF()
            self.update(old)

    def paintEvent(self, event) -> None:
        if self.rect_f.isNull():
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        fill = QColor(self.color)
        fill.setAlphaF(0.45)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(fill)
        p.drawRoundedRect(self.rect_f, 4, 4)
        p.end()


WORD_CHARS = "'’-%"


def _x(line, position: int) -> float:
    result = line.cursorToX(position)
    return float(result[0] if isinstance(result, tuple) else result)


def word_rect(label: QLabel, local: QPointF) -> QRectF | None:
    """Rectangle (in label coordinates) of the word at a point, or None.

    Lays the text out the way QLabel paints plain text (QTextLayout, wrapped at the
    label's content width, each line aligned on its own), so the box sits on the word.
    """
    text = label.text().replace('\n', '\u2028')
    if not text.strip() or label.textFormat() == Qt.TextFormat.RichText or _might_be_rich(text):
        return None
    area = QRectF(label.contentsRect())
    m = label.margin()
    area.adjust(m, m, -m, -m)
    if label.indent() > 0:
        area.adjust(label.indent(), 0, 0, 0)
    align = label.alignment()
    layout = QTextLayout(text, label.font())
    option = QTextOption()
    option.setWrapMode(QTextOption.WrapMode.WordWrap if label.wordWrap() else QTextOption.WrapMode.ManualWrap)
    layout.setTextOption(option)
    leading = QFontMetricsF(label.font()).leading()
    lines = []
    height = 0.0
    layout.beginLayout()
    while True:
        line = layout.createLine()
        if not line.isValid():
            break
        line.setLineWidth(area.width() if label.wordWrap() else 1_000_000)
        height += leading
        line.setPosition(QPointF(0, height))
        height += line.height()
        lines.append(line)
    layout.endLayout()
    y0 = area.y()
    if align & Qt.AlignmentFlag.AlignVCenter:
        y0 += (area.height() - height) / 2
    elif align & Qt.AlignmentFlag.AlignBottom:
        y0 += area.height() - height
    y = local.y() - y0
    line = next((ln for ln in lines if ln.y() <= y < ln.y() + ln.height()), None)
    if line is None:
        return None
    x0 = area.x()
    natural = line.naturalTextWidth()
    if align & Qt.AlignmentFlag.AlignHCenter:
        x0 += (area.width() - natural) / 2
    elif align & Qt.AlignmentFlag.AlignRight:
        x0 += area.width() - natural
    x = local.x() - x0
    if x < 0 or x > natural:
        return None
    result = line.xToCursor(x, QTextLine.CursorPosition.CursorBetweenCharacters)
    pos = int(result[0] if isinstance(result, tuple) else result)
    first, last = line.textStart(), line.textStart() + line.textLength()

    def is_word(i: int) -> bool:
        return first <= i < last and (text[i].isalnum() or text[i] in WORD_CHARS)

    # the character under the pointer is the one whose box contains x
    if pos > first and (pos >= last or _x(line, pos) > x):
        pos -= 1
    if not is_word(pos) or not text[pos].strip():
        return None
    start, stop = pos, pos + 1
    while is_word(start - 1):
        start -= 1
    while is_word(stop):
        stop += 1
    x1, x2 = _x(line, start), _x(line, stop)
    return QRectF(x0 + x1 - 2, y0 + line.y(), max(2.0, x2 - x1) + 4, line.height())


class WordHighlighter(QObject):
    """Follows the pointer and highlights the word under it, in AccessShift windows only."""

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._enabled = False
        self._color = '#FFE07A'
        self._layers: dict[int, _HighlightLayer] = {}
        self._current: _HighlightLayer | None = None
        self._timer = QTimer(self)
        self._timer.setInterval(POLL_MS)
        self._timer.timeout.connect(self._tick)

    @property
    def enabled(self) -> bool:
        return self._enabled

    def set_color(self, color: str) -> None:
        self._color = color

    def set_enabled(self, enabled: bool) -> None:
        self._enabled = bool(enabled)
        if self._enabled:
            self._timer.start()
        else:
            self._timer.stop()
            self._clear()

    def _layer_for(self, window: QWidget) -> _HighlightLayer:
        key = id(window)
        layer = self._layers.get(key)
        if layer is None:
            layer = _HighlightLayer(window)
            self._layers[key] = layer
            window.destroyed.connect(lambda _=None, k=key: self._layers.pop(k, None))
        return layer

    def _clear(self) -> None:
        if self._current is not None:
            self._current.clear()
            self._current = None

    def _tick(self) -> None:
        widget = QApplication.widgetAt(QCursor.pos())
        if not isinstance(widget, QLabel) or not widget.isVisible():
            self._clear()
            return
        rect = word_rect(widget, QPointF(widget.mapFromGlobal(QCursor.pos())))
        if rect is None:
            self._clear()
            return
        window = widget.window()
        layer = self._layer_for(window)
        if self._current is not None and self._current is not layer:
            self._current.clear()
        top_left = widget.mapTo(window, rect.topLeft().toPoint())
        layer.show_rect(QRectF(QRect(top_left, rect.size().toSize())), self._color)
        self._current = layer
