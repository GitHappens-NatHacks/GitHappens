"""Clinical Eye & blink control surfaces: telemetry viewport, posture diagram, dwell gauge."""
from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QPainterPath
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget,
)

from accessshift.ui.control_center_components import Switch

NAVY = QColor('#0B1F3A')
BLUE = QColor('#2F6FED')
SOFT = QColor('#D6E8F8')
ASH = QColor('#334155')
LINE = QColor('#94A3B8')
PAPER = QColor('#F8FAFC')
OK = QColor('#0F766E')
WARN = QColor('#B45309')


class GazeTelemetryViewport(QFrame):
    """High-contrast camera / tracking placeholder with mesh guides and status."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName('telemetryViewport')
        self.setMinimumHeight(260)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._active = False
        self._status = 'STANDBY'
        self._confidence = ''

    def set_tracking_active(self, active: bool) -> None:
        self._active = active
        if active:
            self._status = 'READY'
            self._confidence = 'CONFIDENCE: —'
        else:
            self._status = 'STANDBY'
            self._confidence = ''
        self.update()

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect().adjusted(1, 1, -1, -1)
        p.fillRect(rect, QColor('#0B1220'))
        p.setPen(QPen(NAVY if self._active else QColor('#1E293B'), 2))
        p.drawRoundedRect(rect, 4, 4)

        # Face guide oval + iris boxes (placeholder mesh).
        cx, cy = rect.center().x(), rect.center().y() - 8
        face_w, face_h = rect.width() * 0.42, rect.height() * 0.58
        face = QRectF(cx - face_w / 2, cy - face_h / 2, face_w, face_h)
        pen = QPen(BLUE if self._active else LINE, 1.5, Qt.PenStyle.DashLine)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(face)
        eye_y = cy - face_h * 0.08
        eye_w, eye_h = face_w * 0.16, face_h * 0.08
        left = QRectF(cx - face_w * 0.22, eye_y, eye_w, eye_h)
        right = QRectF(cx + face_w * 0.06, eye_y, eye_w, eye_h)
        p.setPen(QPen(SOFT if self._active else LINE, 1.5))
        p.drawRect(left)
        p.drawRect(right)
        if self._active:
            p.setBrush(BLUE)
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(left.center(), 3, 3)
            p.drawEllipse(right.center(), 3, 3)

        # Crosshair / gaze vector hint.
        p.setPen(QPen(BLUE if self._active else LINE, 1))
        p.drawLine(int(cx), int(face.top() - 12), int(cx), int(face.top() + 8))
        p.drawLine(int(cx - 10), int(face.top() - 2), int(cx + 10), int(face.top() - 2))

        font = QFont('Segoe UI', 11)
        font.setWeight(QFont.Weight.DemiBold)
        p.setFont(font)
        p.setPen(QColor('#E2E8F0'))
        caption = 'Live camera feed' if self._active else 'Camera standby · enable tracking to preview'
        p.drawText(rect.adjusted(14, 12, -14, -12), Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft, caption)

        # Status badges.
        badge = self._status
        badge_bg = OK if self._active else WARN
        bf = QFont('Segoe UI', 10)
        bf.setWeight(QFont.Weight.Bold)
        p.setFont(bf)
        metrics = p.fontMetrics()
        bw = metrics.horizontalAdvance(badge) + 16
        bh = metrics.height() + 8
        badge_rect = QRectF(rect.right() - bw - 12, rect.top() + 12, bw, bh)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(badge_bg)
        p.drawRoundedRect(badge_rect, 3, 3)
        p.setPen(QColor('#FFFFFF'))
        p.drawText(badge_rect, Qt.AlignmentFlag.AlignCenter, badge)
        if self._confidence:
            p.setPen(QColor('#94A3B8'))
            p.setFont(QFont('Segoe UI', 10))
            p.drawText(
                rect.adjusted(14, 0, -14, -14),
                Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignLeft,
                self._confidence,
            )
        p.end()


class GazePostureDiagram(QFrame):
    """Line-art posture / gaze / blink interaction model."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName('postureDiagram')
        self.setMinimumHeight(168)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = self.rect().adjusted(1, 1, -1, -1)
        p.fillRect(r, PAPER)
        p.setPen(QPen(QColor('#E2E8F0'), 1))
        p.drawRoundedRect(r, 4, 4)

        # Screen rectangle (right).
        screen = QRectF(r.width() * 0.58, r.height() * 0.22, r.width() * 0.28, r.height() * 0.42)
        p.setPen(QPen(NAVY, 2))
        p.setBrush(QColor('#FFFFFF'))
        p.drawRoundedRect(screen, 2, 2)
        p.setPen(QPen(BLUE, 1.5))
        p.drawLine(screen.center().x(), screen.top() + 8, screen.center().x(), screen.bottom() - 8)

        # User head (left).
        head_c = QPointF(r.width() * 0.28, r.height() * 0.42)
        p.setPen(QPen(NAVY, 2))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(head_c, 22, 26)
        # Gaze vector.
        p.setPen(QPen(BLUE, 2))
        p.drawLine(head_c + QPointF(18, -4), screen.center())
        # Blink arc around eye.
        p.setPen(QPen(OK, 2))
        path = QPainterPath()
        path.moveTo(head_c + QPointF(-6, -2))
        path.quadTo(head_c + QPointF(0, -10), head_c + QPointF(8, -2))
        p.drawPath(path)

        # Distance bracket.
        p.setPen(QPen(ASH, 1))
        y = r.height() * 0.78
        x0, x1 = r.width() * 0.28, r.width() * 0.72
        p.drawLine(int(x0), int(y), int(x1), int(y))
        p.drawLine(int(x0), int(y - 4), int(x0), int(y + 4))
        p.drawLine(int(x1), int(y - 4), int(x1), int(y + 4))

        font = QFont('Segoe UI', 10)
        font.setWeight(QFont.Weight.DemiBold)
        p.setFont(font)
        p.setPen(ASH)
        p.drawText(QRectF(x0, y + 6, x1 - x0, 18), Qt.AlignmentFlag.AlignCenter, '50–70 cm · gaze vector · blink arc')
        p.setFont(QFont('Segoe UI', 11, QFont.Weight.Bold))
        p.setPen(NAVY)
        p.drawText(r.adjusted(12, 10, -12, -12), Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft, 'Interaction model')
        p.end()


class DwellRingPreview(QWidget):
    """Circular dwell completion preview for the selected dwell duration."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setFixedSize(72, 72)
        self._progress = 0.55
        self._ms = 3000

    def set_dwell_ms(self, ms: int) -> None:
        self._ms = int(ms)
        # Preview ring fills proportionally across the allowed range.
        self._progress = max(0.15, min(1.0, (4200 - self._ms) / 1400 * 0.55 + 0.35))
        self.update()

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(6, 6, 60, 60)
        p.setPen(QPen(QColor('#E2E8F0'), 5))
        p.drawEllipse(rect)
        pen = QPen(BLUE, 5)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(pen)
        span = int(-360 * 16 * self._progress)
        p.drawArc(rect, 90 * 16, span)
        p.setPen(NAVY)
        font = QFont('Segoe UI', 9)
        font.setWeight(QFont.Weight.Bold)
        p.setFont(font)
        p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, f'{self._ms}\nms')
        p.end()


class IconToggleRow(QFrame):
    """Compact clinical toggle row with a drawn glyph, not a nested card stack."""
    changed = Signal(bool)

    def __init__(self, heading: str, details: str, icon: str = 'eye', *, checked: bool = False):
        super().__init__()
        self.setObjectName('clinicalRow')
        self._icon = icon
        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 10, 12, 10)
        lay.setSpacing(12)
        glyph = _IconBadge(icon)
        lay.addWidget(glyph, alignment=Qt.AlignmentFlag.AlignVCenter)
        texts = QVBoxLayout()
        texts.setSpacing(2)
        title = QLabel(heading)
        title.setObjectName('clinicalRowTitle')
        desc = QLabel(details)
        desc.setObjectName('clinicalRowBody')
        desc.setWordWrap(True)
        texts.addWidget(title)
        texts.addWidget(desc)
        lay.addLayout(texts, 1)
        self.switch = Switch(heading)
        self.switch.setFixedSize(52, 28)
        self.switch.setChecked(checked)
        self.switch.toggled.connect(self.changed.emit)
        lay.addWidget(self.switch, alignment=Qt.AlignmentFlag.AlignVCenter)

    def set_value(self, value: bool) -> None:
        self.switch.blockSignals(True)
        self.switch.setChecked(value)
        self.switch.blockSignals(False)


class _IconBadge(QWidget):
    def __init__(self, kind: str):
        super().__init__()
        self._kind = kind
        self.setFixedSize(36, 36)

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(SOFT)
        p.drawRoundedRect(0, 0, 36, 36, 4, 4)
        p.setPen(QPen(NAVY, 1.8))
        p.setBrush(Qt.BrushStyle.NoBrush)
        if self._kind == 'blink':
            path = QPainterPath()
            path.moveTo(8, 18)
            path.quadTo(18, 8, 28, 18)
            path.quadTo(18, 28, 8, 18)
            p.drawPath(path)
            p.setBrush(BLUE)
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(QPointF(18, 18), 3, 3)
        else:
            p.drawEllipse(QPointF(18, 18), 9, 6)
            p.setBrush(NAVY)
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(QPointF(18, 18), 3, 3)
        p.end()


def micro_label(text: str) -> QLabel:
    item = QLabel(text)
    item.setObjectName('clinicalMicro')
    return item


def clinical_title(text: str) -> QLabel:
    item = QLabel(text)
    item.setObjectName('clinicalTitle')
    font = QFont('Segoe UI', 26)
    font.setWeight(QFont.Weight.Bold)
    font.setLetterSpacing(QFont.SpacingType.PercentageSpacing, 98)
    item.setFont(font)
    return item


def dwell_band_label(ms: int) -> str:
    if ms <= 2900:
        return 'Snappy'
    if ms <= 3400:
        return 'Balanced'
    return 'Safe'
