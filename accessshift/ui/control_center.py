"""AccessShift control center: preferences-first desktop UI for macOS and Windows.

This replaces the booking-centric window without touching the demo portal.  It
uses the existing AdaptiveEngine and SteadyHandController APIs.  Platform-side
hooks (camera worker, system pointer, browser extension) are integration tasks,
not capabilities claimed by the UI.
"""
from __future__ import annotations

import time
from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QCursor, QFont, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import (
    QApplication, QComboBox, QFileDialog, QFrame, QGridLayout, QHBoxLayout, QLabel, QLineEdit, QMainWindow,
    QMessageBox, QPushButton, QScrollArea, QSizePolicy, QSlider, QStackedWidget,
    QVBoxLayout, QWidget,
)

from accessshift.engine.adaptive_engine import AdaptiveEngine
from accessshift.modules.smartinterface import (
    ScreenTintManager, VisualPreview, apply_accessshift_appearance,
)
from accessshift.modules.steadyhand.controller import SteadyHandController
from accessshift.modules.steadyhand.metrics import Trial, save_results
from accessshift.modules.steadyhand.targets import Target, TargetManager
from accessshift.ui.control_center_components import (
    PreferenceRow, StatCard, button, card, label,
)
from accessshift.ui.control_center_settings import (
    AccessibilitySettings, PROFILES, load_settings, save_settings,
)
from accessshift.ui import typography as ui_type
from accessshift.ui.gaze_control_panel import (
    DwellRingPreview, GazeTelemetryViewport, dwell_band_label,
)

# Atmosphere photos per page. Spread through sections (never clustered as one gallery).
# soft-keyboard.jpg is excluded: keyboard-only crop without a full display.
PHOTO_SETS = {
    'overview': (
        'desk-laptop-a.jpg', 'cam-bezel.jpg', 'mouse-mat.jpg', 'clinic-light.jpg',
        'screen-glow.jpg', 'audio-desk.jpg', 'window-seat.jpg', 'soft-wall.jpg',
        'read-ready.jpg', 'mug-stack.jpg',
    ),
    'personalize': (
        'pages-light.jpg', 'read-ready.jpg', 'window-seat.jpg', 'desk-top.jpg',
        'clinic-light.jpg', 'mug-stack.jpg', 'open-notebook.jpg', 'desk-laptop-a.jpg',
    ),
    'gaze': (
        'cam-bezel.jpg', 'lens-close.jpg', 'webcam.jpg', 'screen-glow.jpg',
        'soft-wall.jpg', 'care-corner.jpg', 'clinic-light.jpg', 'desk-laptop-a.jpg',
    ),
    'steady': (
        'mouse-mat.jpg', 'desk-top.jpg', 'soft-mouse.jpg', 'screen-glow.jpg',
        'pages-light.jpg', 'desk-laptop-a.jpg', 'light-field.jpg', 'mug-stack.jpg',
    ),
    'interface': (
        'screen-glow.jpg', 'desk-laptop-a.jpg', 'clinic-light.jpg', 'soft-wall.jpg',
        'wide-light.jpg', 'pages-light.jpg', 'care-corner.jpg', 'window-seat.jpg',
    ),
    'speech': (
        'audio-desk.jpg', 'read-ready.jpg', 'pages-light.jpg', 'care-corner.jpg',
        'lens-close.jpg', 'soft-wall.jpg', 'clinic-light.jpg', 'mug-stack.jpg',
    ),
    'test': (
        'mouse-mat.jpg', 'desk-top.jpg', 'desk-laptop-a.jpg', 'cam-bezel.jpg',
        'screen-glow.jpg', 'light-field.jpg', 'clinic-light.jpg', 'pages-light.jpg',
    ),
}

FEATURE_PHOTOS = {
    'gaze_control': 'cam-bezel.jpg',
    'steady_hand': 'mouse-mat.jpg',
    'smart_interface': 'screen-glow.jpg',
    'predictive_speech': 'audio-desk.jpg',
}

SEQUENCE = ('doctor', 'date', 'time', 'review', 'book') * 2
LABELS = {
    'doctor': '1. Doctor',
    'date': '2. Date',
    'time': '3. Time',
    'review': '4. Review',
    'book': '5. Book',
}


def _fit_pixmap(pix: QPixmap, size, *, fill: QColor | None = None) -> tuple[QPixmap, int, int]:
    """Scale a photo to fit inside size without cropping. Returns (scaled, x, y)."""
    if pix.isNull() or size.width() < 1 or size.height() < 1:
        return QPixmap(), 0, 0
    scaled = pix.scaled(
        size,
        Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )
    x = (size.width() - scaled.width()) // 2
    y = (size.height() - scaled.height()) // 2
    return scaled, x, y


class _FitPhoto(QWidget):
    """Shows the full photo letterboxed; never crops edges for a fill crop."""

    def __init__(self, pixmap: QPixmap, height: int = 360):
        super().__init__()
        self._pix = pixmap
        self.setObjectName('atmosphereImage')
        self.setMinimumHeight(height)
        self.setMaximumHeight(height)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def paintEvent(self, event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        p.fillRect(self.rect(), QColor('#E8EEF5'))
        scaled, x, y = _fit_pixmap(self._pix, self.size())
        if not scaled.isNull():
            p.drawPixmap(x, y, scaled)
        p.end()


class FeatureTile(QFrame):
    """Full-width dashboard feature with photo background and high-contrast copy."""

    activated = Signal()

    def __init__(
        self,
        title: str,
        description: str,
        pixmap: QPixmap,
        *,
        primary: bool = False,
        cue: str = '',
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self._pix = pixmap
        self._title = title
        self._description = description
        self._cue = cue
        self._primary = primary
        self._active = False
        self.setObjectName('featureTilePrimary' if primary else 'featureTile')
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(260 if primary else 168)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.status = label('Off', 'featureTileStatus')
        self.status.hide()  # painted; kept for _refresh text updates

    def set_active(self, enabled: bool) -> None:
        self._active = bool(enabled)
        self.status.setText('On' if enabled else 'Off')
        self.setProperty('active', self._active)
        self.update()

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self.activated.emit()
        super().mouseReleaseEvent(event)

    def paintEvent(self, event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        rect = self.rect().adjusted(1, 1, -1, -1)
        radius = 20 if self._primary else 16
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor('#0B1F3A'))
        p.drawRoundedRect(rect, radius, radius)
        if not self._pix.isNull():
            scaled = self._pix.scaled(
                QSize(max(1, int(rect.width())), max(1, int(rect.height()))),
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )
            x = rect.x() + (rect.width() - scaled.width()) / 2
            y = rect.y() + (rect.height() - scaled.height()) / 2
            clip = QPainterPath()
            clip.addRoundedRect(rect, radius, radius)
            p.setClipPath(clip)
            p.drawPixmap(int(x), int(y), scaled)
            p.setClipping(False)
        # Strong scrim so title and body stay readable on any photo.
        scrim = QColor(5, 14, 28, 188 if self._primary else 176)
        p.fillRect(rect, scrim)
        if self._active:
            p.setPen(QPen(QColor('#2F6FED'), 4))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRoundedRect(rect.adjusted(2, 2, -2, -2), radius, radius)

        margin = 28 if self._primary else 22
        ink = QColor('#FFFFFF')
        muted = QColor('#D6E8F8')
        p.setPen(ink)
        title_size = 34 if self._primary else 24
        p.setFont(QFont(ui_type.DISPLAY_FAMILY, title_size, QFont.Weight.ExtraLight))
        title_rect = QRectF(margin, margin, rect.width() - margin * 2, 48 if self._primary else 40)
        p.drawText(title_rect, int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter), self._title)

        p.setPen(muted)
        body_size = 16 if self._primary else 14
        p.setFont(QFont(ui_type.BODY_FAMILY, body_size, QFont.Weight.Normal))
        body_top = margin + (52 if self._primary else 44)
        footer = 36 if self._cue else 8
        body_rect = QRectF(
            margin, body_top,
            rect.width() - margin * 2 - 100,
            rect.height() - body_top - margin - footer,
        )
        p.drawText(
            body_rect,
            int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop | Qt.TextFlag.TextWordWrap),
            self._description,
        )

        badge = 'On' if self._active else 'Off'
        p.setFont(QFont(ui_type.BODY_FAMILY, 13, QFont.Weight.DemiBold))
        badge_w, badge_h = 64, 28
        badge_rect = QRectF(rect.right() - margin - badge_w, margin, badge_w, badge_h)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor('#2F6FED') if self._active else QColor(255, 255, 255, 40))
        p.drawRoundedRect(badge_rect, 980, 980)
        p.setPen(ink)
        p.drawText(badge_rect, int(Qt.AlignmentFlag.AlignCenter), badge)

        if self._cue:
            p.setPen(QColor('#A8C8F0'))
            p.setFont(QFont(ui_type.BODY_FAMILY, 14, QFont.Weight.DemiBold))
            cue_rect = QRectF(margin, rect.bottom() - margin - 22, rect.width() - margin * 2, 24)
            p.drawText(cue_rect, int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter), self._cue)
        p.end()


class _PhotoTextBand(QWidget):
    """Full-width editorial photo (uncropped fit) with title over a soft navy scrim."""

    def __init__(self, pixmap: QPixmap, title: str, subtitle: str, height: int = 420):
        super().__init__()
        self._pix = pixmap
        self._title = title
        self._subtitle = subtitle
        self.setMinimumHeight(height)
        self.setMaximumHeight(height)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setAccessibleName(title)

    def paintEvent(self, event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        rect = self.rect()
        p.fillRect(rect, QColor('#0B1F3A'))
        scaled, x, y = _fit_pixmap(self._pix, rect.size())
        if not scaled.isNull():
            p.drawPixmap(x, y, scaled)
        scrim_h = min(180, max(130, rect.height() // 3))
        scrim = QRectF(0, rect.height() - scrim_h, rect.width(), scrim_h)
        p.fillRect(scrim, QColor(11, 31, 58, 180))
        p.setPen(QColor('#F5F5F7'))
        title_font = QFont(ui_type.DISPLAY_FAMILY, 34, QFont.Weight.ExtraLight)
        p.setFont(title_font)
        text_rect = QRectF(36, rect.height() - scrim_h + 24, rect.width() - 72, 52)
        p.drawText(text_rect, int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter), self._title)
        if self._subtitle:
            body_font = QFont(ui_type.BODY_FAMILY, 15, QFont.Weight.Normal)
            p.setFont(body_font)
            p.setPen(QColor('#D6E8F8'))
            body_rect = QRectF(36, rect.height() - scrim_h + 76, min(720, rect.width() - 72), 60)
            p.drawText(
                body_rect,
                int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop | Qt.TextFlag.TextWordWrap),
                self._subtitle,
            )
        p.end()


class TremorPlayground(QWidget):
    """In-app tremor smoothing and target assistance evaluation canvas.

    Supports baseline, smoothing, target assistance, and combined modes with
    healthcare workflow targets, live accuracy metrics, and JSON trial export.
    """
    metrics_changed = Signal(int, int)
    trial_progress = Signal(object, object)
    trial_completed = Signal(object)

    MODES = [
        'Baseline (Raw input)',
        'SteadyHand smoothing',
        'Target assistance',
        'Smoothing + Target assistance',
    ]

    def __init__(self, controller: SteadyHandController, target_padding: float = 16.0):
        super().__init__()
        self.controller = controller
        self.setMinimumHeight(300)
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.setAccessibleName('SteadyHand accuracy practice and evaluation canvas')

        self.target_manager = TargetManager(padding=target_padding)
        self._mode_index = 3
        self.use_filter = True
        self.assisted = True

        self._inside = False
        self._mouse = (150.0, 130.0)
        self._raw = self._mouse
        self._stable = self._mouse
        self._hits = 0
        self._misses = 0
        self._simulated = True
        self._sim_start = time.perf_counter()

        self.trial: Trial | None = None
        self.results: list[Trial] = []

        self.timer = QTimer(self)
        self.timer.setInterval(30)
        self.timer.timeout.connect(self._tick)
        self.timer.start()
        self._rebuild_targets()

    def set_target_padding(self, padding: float) -> None:
        self.target_manager.padding = max(0.0, float(padding))
        self.update()

    def set_mode(self, mode_index: int) -> None:
        self._mode_index = max(0, min(len(self.MODES) - 1, mode_index))
        self.use_filter = self._mode_index in (1, 3)
        self.assisted = self._mode_index in (2, 3)
        self.controller.enabled = self.use_filter
        self.controller.reset()
        self.update()

    def start_trial(self) -> None:
        self.set_mode(self._mode_index)
        self.trial = Trial(self.MODES[self._mode_index], SEQUENCE)
        self.controller.reset()
        self._sim_start = time.perf_counter()
        self.update()
        self.trial_progress.emit(self.trial.summary(), self.trial.expected)

    def abort_trial(self) -> None:
        if self.trial and not self.trial.complete:
            self.trial = None
            self.update()

    def set_simulation(self, enabled: bool) -> None:
        self._simulated = enabled
        self._sim_start = time.perf_counter()
        self.controller.simulate_tremor = False
        self.update()

    def reset_scores(self) -> None:
        self._hits = 0
        self._misses = 0
        self.metrics_changed.emit(0, 0)
        self.update()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._rebuild_targets()

    def _rebuild_targets(self) -> None:
        w = max(400, self.width())
        h = max(200, self.height())
        btn_w = max(80.0, min(120.0, (w - 70) / 5.0 - 10.0))
        btn_h = max(36.0, min(48.0, h * 0.16))
        margin = 35.0
        avail_w = w - 2 * margin
        step_x = (avail_w - btn_w) / 4.0 if avail_w > btn_w else 90.0
        base_y = h * 0.46
        targets = []
        for i, key in enumerate(('doctor', 'date', 'time', 'review', 'book')):
            x = margin + i * step_x
            y = base_y + ((-1) ** i) * (btn_h * 0.42)
            targets.append(Target(key, LABELS[key], x, y, btn_w, btn_h))
        self.target_manager.set_targets(targets)

    def _tick(self) -> None:
        if not self.isVisible():
            return
        x, y = self._mouse
        now = time.perf_counter()
        if self._simulated:
            dx, dy = self.controller.tremor_offset(now - self._sim_start)
            x += dx
            y += dy
        self._raw = (x, y)
        self._stable = self.controller.stabilize(x, y, now) if self.use_filter else (x, y)
        self.update()

    def mouseMoveEvent(self, event) -> None:
        p = event.position()
        self._mouse = (p.x(), p.y())
        self._inside = True
        super().mouseMoveEvent(event)

    def leaveEvent(self, event) -> None:
        self._inside = False
        super().leaveEvent(event)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            sx, sy = self._stable
            target = self.target_manager.select(sx, sy, assisted=self.assisted)
            if self.trial and not self.trial.complete:
                hit = self.trial.record(target.id if target else None, sx, sy)
                if hit:
                    self._hits += 1
                else:
                    self._misses += 1
                self.metrics_changed.emit(self._hits, self._misses)
                self.trial_progress.emit(self.trial.summary(), self.trial.expected)
                if self.trial.complete:
                    self.results.append(self.trial)
                    self.trial_completed.emit(self.trial)
            else:
                if target is not None:
                    self._hits += 1
                else:
                    self._misses += 1
                self.metrics_changed.emit(self._hits, self._misses)
        super().mousePressEvent(event)

    def hideEvent(self, event) -> None:
        self.timer.stop()
        super().hideEvent(event)

    def showEvent(self, event) -> None:
        if not self.timer.isActive():
            self.timer.start()
        super().showEvent(event)

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor('#F4F7FB'))
        p.drawRoundedRect(self.rect().adjusted(0, 0, -1, -1), 14, 14)
        p.setPen(QPen(QColor('#D7E0EC'), 1))
        for gx in range(25, self.width(), 30):
            for gy in range(25, self.height(), 30):
                p.drawPoint(gx, gy)

        expected_id = self.trial.expected if (self.trial and not self.trial.complete) else None
        sx, sy = self._stable
        candidate = self.target_manager.select(sx, sy, assisted=self.assisted) if self._inside else None
        pad = self.target_manager.padding

        for t in self.target_manager.targets:
            rect = QRectF(t.x, t.y, t.width, t.height)
            if self.assisted and pad > 0:
                p.setPen(QPen(QColor('#9BB8E8'), 1, Qt.PenStyle.DashLine))
                p.setBrush(QColor('#E8F0FE'))
                p.drawRoundedRect(rect.adjusted(-pad, -pad, pad, pad), 9, 9)
            is_expected = t.id == expected_id
            if is_expected:
                p.setPen(QPen(QColor('#2F6FED'), 2))
                p.setBrush(QColor('#D6E8F8'))
            else:
                p.setPen(QPen(QColor('#B8C9DE'), 1))
                p.setBrush(QColor('#FFFFFF'))
            p.drawRoundedRect(rect, 7, 7)
            p.setPen(QColor('#0B1F3A' if is_expected else '#3E5370'))
            font = p.font()
            font.setBold(is_expected)
            font.setPointSize(10)
            p.setFont(font)
            p.drawText(rect, Qt.AlignmentFlag.AlignCenter, t.label)
            if candidate and candidate.id == t.id:
                p.setPen(QPen(QColor('#0B1F3A'), 2))
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.drawRoundedRect(rect.adjusted(-3, -3, 3, 3), 9, 9)

        if self._inside:
            rx, ry = self._raw
            if self._simulated or self.use_filter:
                p.setPen(QPen(QColor('#5A6F8A'), 2))
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.drawEllipse(QPointF(rx, ry), 9, 9)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor('#2F6FED'))
            p.drawEllipse(QPointF(sx, sy), 5, 5)

        p.setPen(QColor('#5A6F8A'))
        font = p.font()
        font.setPointSize(9)
        font.setBold(False)
        p.setFont(font)
        status_text = f'EVALUATION PLAYGROUND  •  Mode: {self.MODES[self._mode_index]}'
        if self.trial and not self.trial.complete:
            status_text += f'  •  Target {self.trial.index + 1}/10: {LABELS.get(self.trial.expected, "")}'
        p.drawText(16, 22, status_text)
        p.drawText(
            16,
            self.height() - 12,
            'Grey ring = Raw pointer with tremor   •   Blue dot = Stabilized / assisted pointer   •   Navy outline = Selected candidate',
        )
        p.end()


class MainWindow(QMainWindow):
    """Drop-in replacement for accessshift.ui.main_window.MainWindow(repo_root)."""

    preferences_changed = Signal(object)  # dict; app services may subscribe
    calibration_requested = Signal()  # gaze team can connect worker/controller
    assistance_changed = Signal(bool)

    def __init__(self, repo_root: Path):
        super().__init__()
        self.repo_root = Path(repo_root)
        ui_type.ensure_fonts(self.repo_root)
        self.prefs = load_settings()
        self.engine = AdaptiveEngine(self)
        self.steady = SteadyHandController()
        self.speech = None  # instantiated only when the user presses Speak
        self._nav = {}
        self._pages = {}
        self._toggle_rows = {}
        self._sliders = {}
        self._preset_buttons = {}
        self._module_cells = {}
        self._base_qss = Path(__file__).with_name('control_center_styles.qss').read_text(encoding='utf-8')
        self.tint_manager = ScreenTintManager(QApplication.instance())
        self._syncing_engine = True
        self._build_ui()
        self.tint_manager.register_window(self)  # Restrict tint to this application window
        self.engine.modules_changed.connect(self._on_external_modules_changed)
        self._apply_preferences_to_engine()
        self._syncing_engine = False
        self._refresh()
        self._navigate('overview' if self.prefs.initial_setup_complete else 'personalize')
        self.resize(1280, 860)
        self.setMinimumSize(960, 680)
        self.setWindowTitle('AccessShift AI  ·  Accessibility Settings')
        self._apply_visual_preferences()

    def _build_ui(self):
        root = QWidget()
        root.setObjectName('appRoot')
        self.setCentralWidget(root)
        outer = QVBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Top chrome replaces the left rail; gaze focus still hides it via self.sidebar.
        header = QFrame()
        header.setObjectName('siteHeader')
        self.sidebar = header
        head = QHBoxLayout(header)
        head.setContentsMargins(28, 14, 28, 14)
        head.setSpacing(12)

        left = QWidget()
        left_l = QHBoxLayout(left)
        left_l.setContentsMargins(0, 0, 0, 0)
        left_l.setSpacing(6)
        brand = label('AccessShift', 'brandMark')
        brand.setFont(QFont(ui_type.DISPLAY_FAMILY, 28, QFont.Weight.ExtraLight))
        left_l.addWidget(brand)
        left_l.addWidget(label('·', 'brandDot'))
        left_l.addStretch(1)

        # Compact nav cluster: buttons stay packed; outer stretches absorb width.
        nav_cluster = QWidget()
        nav_cluster.setObjectName('navCluster')
        nav_cluster.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Preferred)
        center_l = QHBoxLayout(nav_cluster)
        center_l.setContentsMargins(0, 0, 0, 0)
        center_l.setSpacing(0)
        nav_entries = [
            ('overview', 'Home', 'navButton'),
            ('gaze', 'HeadPoint', 'navPrimaryButton'),
            ('steady', 'SteadyHand', 'navPrimaryButton'),
            ('interface', 'Reading', 'navButton'),
            ('speech', 'Speech', 'navButton'),
            ('test', 'Try demos', 'navButton'),
        ]
        for key, text, role in nav_entries:
            nav_button = button(text, role)
            nav_button.setCheckable(True)
            nav_button.setMinimumHeight(40)
            nav_button.setCursor(Qt.CursorShape.PointingHandCursor)
            nav_button.clicked.connect(lambda _, k=key: self._navigate(k))
            nav_button.setAccessibleName(text)
            center_l.addWidget(nav_button)
            self._nav[key] = nav_button

        right = QWidget()
        right.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Preferred)
        right_l = QHBoxLayout(right)
        right_l.setContentsMargins(0, 0, 0, 0)
        right_l.setSpacing(10)
        right_l.addWidget(label('Local demo', 'topBarBadge'))
        profile_btn = button('Profile', 'profileNavButton')
        profile_btn.setCheckable(True)
        profile_btn.setMinimumHeight(40)
        profile_btn.setMinimumWidth(104)
        profile_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        profile_btn.setAccessibleName('Profile')
        profile_btn.clicked.connect(lambda: self._navigate('personalize'))
        right_l.addWidget(profile_btn)
        self._nav['personalize'] = profile_btn

        left.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Preferred)
        head.addWidget(left, 0)
        head.addStretch(1)
        head.addWidget(nav_cluster, 0)
        head.addStretch(1)
        head.addWidget(right, 0)
        self.top_bar_layout = right_l
        outer.addWidget(header)

        right = QWidget()
        self.workspace = right
        right_l = QVBoxLayout(right)
        right_l.setContentsMargins(0, 0, 0, 0)
        right_l.setSpacing(0)
        self.stack = QStackedWidget()
        right_l.addWidget(self.stack, 1)
        for key, method in [
            ('overview', self._page_overview),
            ('personalize', self._page_personalize),
            ('gaze', self._page_gaze),
            ('steady', self._page_steady),
            ('interface', self._page_interface),
            ('speech', self._page_communication),
            ('test', self._page_test),
        ]:
            page = method()
            self._pages[key] = page
            self.stack.addWidget(page)
        foot = QFrame()
        foot.setObjectName('footerBar')
        fl = QHBoxLayout(foot)
        fl.setContentsMargins(28, 12, 28, 12)
        fl.addWidget(label('AccessShift AI  ·  Local accessibility prototype', 'footerText'))
        fl.addStretch()
        self.footer_status = label('Preferences saved locally', 'footerText')
        fl.addWidget(self.footer_status)
        right_l.addWidget(foot)
        outer.addWidget(right, 1)

    def _page(self, title, subtitle):
        scroller = QScrollArea()
        scroller.setWidgetResizable(True)
        scroller.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        container = QWidget()
        container.setObjectName('scrollContent')
        content = QVBoxLayout(container)
        content.setContentsMargins(64, 48, 64, 64)
        content.setSpacing(28)
        title_label = label(title, 'pageTitle')
        title_label.setFont(QFont(ui_type.DISPLAY_FAMILY, 56, QFont.Weight.ExtraLight))
        title_label.setAccessibleName(title)
        content.addWidget(title_label)
        content.addSpacing(8)
        desc = label(subtitle, 'pageDescription', True)
        desc.setMaximumWidth(720)
        content.addWidget(desc)
        content.addSpacing(20)
        scroller.setWidget(container)
        return scroller, content

    def _section(self, lay, title, subtitle=None):
        section = label(title, 'sectionTitle')
        section.setFont(QFont(ui_type.DISPLAY_FAMILY, 32, QFont.Weight.ExtraLight))
        lay.addWidget(section)
        if subtitle:
            sub = label(subtitle, 'bodyText', True)
            sub.setMaximumWidth(640)
            lay.addWidget(sub)
        lay.addSpacing(8)

    def _photos(self, key: str) -> list[str]:
        files = [f for f in PHOTO_SETS.get(key, PHOTO_SETS['overview']) if f != 'soft-keyboard.jpg']
        return files or list(PHOTO_SETS['overview'])

    def _load_photo(self, filename: str) -> QPixmap:
        path = self.repo_root / 'assets' / 'ui' / filename
        return QPixmap(str(path)) if path.is_file() else QPixmap()

    def _photo_label(self, filename: str, height: int = 360) -> _FitPhoto:
        return _FitPhoto(self._load_photo(filename), height=height)

    def _photo_band(self, lay, filename: str, height: int = 400) -> None:
        """One wide photo between content blocks; full frame visible, no crop."""
        lay.addWidget(self._photo_label(filename, height))
        lay.addSpacing(8)

    def _photo_pair(self, lay, left: str, right: str, height: int = 300) -> None:
        row = QHBoxLayout()
        row.setSpacing(18)
        row.addWidget(self._photo_label(left, height), 1)
        row.addWidget(self._photo_label(right, height), 1)
        lay.addLayout(row)
        lay.addSpacing(8)

    def _text_on_photo(self, lay, filename: str, title: str, subtitle: str = '', height: int = 400) -> None:
        """Large photo as background with related copy; image fits without cropping."""
        band = _PhotoTextBand(self._load_photo(filename), title, subtitle, height)
        lay.addWidget(band)
        lay.addSpacing(16)

    def _atmosphere(self, lay, filename: str, height: int = 280) -> None:
        self._photo_band(lay, filename, height)

    def _page_overview(self):
        page, lay = self._page(
            'Accessibility, your way.',
            'Configure your tools, preview your changes, and return whenever you need.',
        )
        shots = self._photos('overview')
        self._text_on_photo(
            lay, shots[0],
            'Make every interaction easier.',
            'Fine-tune eye control, mouse stabilization, visual accessibility and communication in one place.',
            height=460,
        )
        action_row = QHBoxLayout()
        action_row.setSpacing(16)
        self.overview_profile = label('Your setup: Custom', 'heroBadge')
        action_row.addWidget(self.overview_profile)
        action_row.addStretch(1)
        edit = button('Customize profile', 'heroButton')
        edit.setMinimumHeight(48)
        edit.setMinimumWidth(200)
        edit.clicked.connect(lambda: self._navigate('personalize'))
        action_row.addWidget(edit)
        lay.addLayout(action_row)
        lay.addSpacing(20)

        self._photo_band(lay, shots[1], 380)
        self._section(
            lay,
            'Start here',
            'HeadPoint and SteadyHand are the two main tools. Open a card, then use Calibrate or Try demo.',
        )
        self.overview_module_labels = {}
        self._module_cells = {}
        primary = [
            ('gaze_control', 'HeadPoint',
             'Point with your head. Look at a button, then blink or wait to select it.',
             'gaze', 'Open · Calibrate · Try booking demo'),
            ('steady_hand', 'SteadyHand',
             'Steady a shaky pointer and make buttons easier to hit.',
             'steady', 'Open · Adjust · Try SteadyHand demo'),
        ]
        for key, title_text, desc, page_key, cue in primary:
            tile = FeatureTile(
                title_text, desc, self._load_photo(FEATURE_PHOTOS[key]),
                primary=True, cue=cue,
            )
            tile.activated.connect(lambda k=page_key: self._navigate(k))
            lay.addWidget(tile)
            lay.addSpacing(14)
            self._module_cells[key] = tile
            self.overview_module_labels[key] = tile.status

        # Always-visible shortcuts so calibration and demos are not buried.
        shortcuts = QHBoxLayout()
        shortcuts.setSpacing(12)
        cal_now = button('Calibrate HeadPoint', 'primaryButton')
        cal_now.setMinimumHeight(52)
        cal_now.clicked.connect(self._try_headpoint_calibrate)
        try_head = button('Try HeadPoint demo', 'secondaryButton')
        try_head.setMinimumHeight(52)
        try_head.clicked.connect(self._try_headpoint_demo)
        try_steady = button('Try SteadyHand demo', 'secondaryButton')
        try_steady.setMinimumHeight(52)
        try_steady.clicked.connect(self._try_steady_demo)
        shortcuts.addWidget(cal_now, 1)
        shortcuts.addWidget(try_head, 1)
        shortcuts.addWidget(try_steady, 1)
        lay.addLayout(shortcuts)
        lay.addSpacing(20)

        self._photo_pair(lay, shots[2], shots[3], 300)
        self._section(
            lay,
            'Also available',
            'Extra helpers. Useful, but secondary to HeadPoint and SteadyHand.',
        )
        secondary = [
            ('smart_interface', 'Easier reading',
             'Make the appointment form larger and clearer.',
             'interface'),
            ('predictive_speech', 'Speech',
             'Type a message and hear it spoken aloud.',
             'speech'),
        ]
        for key, title_text, desc, page_key in secondary:
            tile = FeatureTile(
                title_text, desc, self._load_photo(FEATURE_PHOTOS[key]), primary=False,
            )
            tile.activated.connect(lambda k=page_key: self._navigate(k))
            lay.addWidget(tile)
            lay.addSpacing(12)
            self._module_cells[key] = tile
            self.overview_module_labels[key] = tile.status
        lay.addSpacing(12)
        self._photo_pair(lay, shots[8], shots[9], 280)

        row = QHBoxLayout()
        row.setSpacing(16)
        self.stat_modules = StatCard('Selected features', '0 / 4', 'In your current profile')
        self.stat_profile = StatCard('Current profile', 'Custom', 'Edit whenever you like')
        self.stat_platform = StatCard('Demo environment', 'Local only', 'macOS + Windows')
        for w in (self.stat_modules, self.stat_profile, self.stat_platform):
            row.addWidget(w, 1)
        lay.addLayout(row)
        lay.addSpacing(20)
        self._text_on_photo(
            lay, shots[4],
            'Built for calm focus.',
            'Quiet rooms, clear targets, and settings that stay local on this machine.',
            height=400,
        )
        self._photo_pair(lay, shots[5], shots[6], 300)
        self._photo_band(lay, shots[7], 340)

        note, nl = card(name='innerCard', margins=24)
        nl.setSpacing(12)
        nl.addWidget(label('Prototype status', 'cardTitle'))
        nl.addWidget(label(
            'Your settings and local demos work inside AccessShift. Webcam navigation and OS-level pointer control '
            'are separate team integrations. SmartInterface adapts only the bundled healthcare Demo Lab, '
            'not third-party websites.',
            'bodyText', True,
        ))
        lay.addWidget(note)
        lay.addStretch()
        return page

    def _page_personalize(self):
        page, lay = self._page(
            'My accessibility profile',
            'Start from a preset or choose a custom mix. These are preferences, not diagnoses.',
        )
        shots = self._photos('personalize')
        self._text_on_photo(
            lay, shots[0],
            'Your setup, your pace.',
            'Presets are starting points. Everything stays editable.',
            height=420,
        )
        self._section(lay, 'Start with a setup')
        grid = QGridLayout()
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(16)
        for i, (key, p) in enumerate(PROFILES.items()):
            name = p['label']
            description = p['description']
            btn = button(f'{name}\n\n{description}', 'presetButton')
            btn.setCheckable(True)
            btn.setMinimumHeight(110)
            btn.setMinimumWidth(280)
            btn.clicked.connect(lambda _, k=key: self._apply_profile(k))
            grid.addWidget(btn, i // 2, i % 2)
            self._preset_buttons[key] = btn
        lay.addLayout(grid)
        lay.addSpacing(20)
        self._photo_pair(lay, shots[1], shots[2], 320)
        self._photo_band(lay, shots[3], 380)
        self._section(lay, 'Fine-tune your assistance')
        options = [
            ('gaze_control', 'HeadPoint', 'Point with your head and select buttons by looking.'),
            ('steady_hand', 'SteadyHand', 'Smooth shaky mouse movement and enlarge targets.'),
            ('smart_interface', 'Easier reading', 'Simplify the appointment form in Demo Lab.'),
            ('predictive_speech', 'Speech', 'Speak a typed message aloud.'),
        ]
        for key, name, desc in options:
            r = PreferenceRow(name, desc)
            r.changed.connect(lambda value, k=key: self._change_module(k, value))
            self._toggle_rows[key] = r
            lay.addWidget(r)
            lay.addSpacing(10)
        self._text_on_photo(
            lay, shots[4],
            'Save when it feels right.',
            'Return to Home any time. Preferences stay on this device.',
            height=360,
        )
        self._photo_pair(lay, shots[5], shots[6], 300)
        self._photo_band(lay, shots[7], 340)
        actions = QHBoxLayout()
        actions.setContentsMargins(0, 16, 0, 8)
        actions.addStretch()
        done = button('Save profile & return to dashboard', 'primaryButton')
        done.setMinimumHeight(48)
        done.setMinimumWidth(280)
        done.clicked.connect(self._finish_setup)
        actions.addWidget(done)
        lay.addLayout(actions)
        lay.addStretch()
        return page

    def _page_gaze(self):
        page, lay = self._page(
            'HeadPoint',
            'Point with your head. Calibrate once, then try the booking demo.',
        )
        shots = self._photos('gaze')
        self._photo_band(lay, shots[0], 280)

        # Keep clinical widgets for refresh hooks; do not show the busy telemetry UI.
        self.gaze_viewport = GazeTelemetryViewport()
        self.gaze_viewport.hide()
        self.dwell_gauge = DwellRingPreview()
        self.dwell_gauge.hide()

        actions = QHBoxLayout()
        actions.setSpacing(12)
        cal_btn = button('1 · Calibrate', 'primaryButton')
        cal_btn.setMinimumHeight(56)
        cal_btn.clicked.connect(self._try_headpoint_calibrate)
        demo_btn = button('2 · Try booking demo', 'heroButton')
        demo_btn.setMinimumHeight(56)
        demo_btn.clicked.connect(self._try_headpoint_demo)
        actions.addWidget(cal_btn, 1)
        actions.addWidget(demo_btn, 1)
        lay.addLayout(actions)
        lay.addWidget(label(
            'Calibrate first. Then start the demo to book a sample visit by looking at large buttons.',
            'bodyText', True,
        ))
        lay.addSpacing(18)

        self.gaze_toggle = PreferenceRow(
            'Turn on HeadPoint',
            'Move your head to point at buttons on the screen.',
        )
        self.gaze_toggle.changed.connect(self._on_gaze_toggle)
        lay.addWidget(self.gaze_toggle)
        lay.addSpacing(10)

        self.blink_row = PreferenceRow(
            'Blink to confirm',
            'Blink once when you want to press the highlighted button.',
        )
        self.blink_row.changed.connect(lambda v: self._change_option('blink_select', v))
        lay.addWidget(self.blink_row)
        lay.addSpacing(16)

        timing, tl = card(margins=28, spacing=14)
        tl.addWidget(label('How long to look', 'sectionTitle'))
        tl.addWidget(label(
            'Move toward Slow if buttons click too soon. Move toward Fast if waiting feels long.',
            'bodyText', True,
        ))
        self.dwell_slider, dwell_row = self._slider(2800, 4200, 100, 'gaze_dwell_ms', 'ms')
        self.dwell_band = label('Medium', 'pill')
        dwell_row.addWidget(self.dwell_band)
        tl.addLayout(dwell_row)
        pace = QHBoxLayout()
        pace.addWidget(label('Fast', 'subtle'))
        pace.addStretch(1)
        pace.addWidget(label('Slow', 'subtle'))
        tl.addLayout(pace)
        self.dwell_slider.valueChanged.connect(self._on_dwell_preview)
        lay.addWidget(timing)
        lay.addSpacing(20)
        self._photo_band(lay, shots[1], 260)
        lay.addStretch()
        return page

    def _page_steady(self):
        page, lay = self._page(
            'SteadyHand',
            'Steady a shaky pointer. Try the practice demo any time.',
        )
        shots = self._photos('steady')
        self._photo_band(lay, shots[0], 280)

        actions = QHBoxLayout()
        actions.setSpacing(12)
        demo_btn = button('Try SteadyHand demo', 'primaryButton')
        demo_btn.setMinimumHeight(56)
        demo_btn.clicked.connect(self._try_steady_demo)
        actions.addWidget(demo_btn, 1)
        actions.addStretch(1)
        lay.addLayout(actions)
        lay.addWidget(label(
            'The demo lets you practice clicking with simulated shaky movement.',
            'bodyText', True,
        ))
        lay.addSpacing(16)

        row = PreferenceRow('Turn on SteadyHand', 'Smooth the pointer when the helper is active.')
        row.changed.connect(lambda v: self._change_module('steady_hand', v))
        self.steady_toggle = row
        lay.addWidget(row)
        lay.addSpacing(12)
        config, cfg = card(margins=28, spacing=14)
        cfg.addWidget(label('How strong', 'sectionTitle'))
        cfg.addWidget(label('Higher steadies more, but may feel slower.', 'bodyText', True))
        self.strength_slider, sr = self._slider(0, 100, 5, 'tremor_strength', '%')
        cfg.addLayout(sr)
        cfg.addSpacing(12)
        cfg.addWidget(label('Button size', 'cardTitle'))
        cfg.addWidget(label('Larger targets are easier to hit.', 'bodyText'))
        self.target_slider, tr = self._slider(100, 200, 10, 'target_size_pct', '%')
        cfg.addLayout(tr)
        lay.addWidget(config)
        lay.addSpacing(16)
        self._photo_pair(lay, shots[1], shots[2], 260)
        info, il = card(name='innerCard', margins=24, spacing=12)
        il.addWidget(label('Note', 'cardTitle'))
        il.addWidget(label(
            'SteadyHand works inside AccessShift demos. It does not take over your whole computer mouse.',
            'bodyText', True,
        ))
        lay.addWidget(info)
        lay.addStretch()
        return page

    def _page_interface(self):
        page, lay = self._page(
            'Easier reading',
            'Make the Demo Lab form larger, clearer, and calmer. Other apps are not changed.',
        )
        shots = self._photos('interface')
        self._photo_band(lay, shots[0], 300)
        row = PreferenceRow(
            'Simplify the Demo Lab form',
            'Hide side panels and show one step at a time.',
        )
        row.changed.connect(lambda v: self._change_module('smart_interface', v))
        self.interface_toggle = row
        lay.addWidget(row)
        lay.addSpacing(10)
        self.simple_row = PreferenceRow(
            'One step at a time',
            'Show patient, visit, time, then review as separate steps.',
        )
        self.simple_row.changed.connect(lambda v: self._change_option('reduce_complexity', v))
        lay.addWidget(self.simple_row)
        lay.addSpacing(16)

        options, ol = card(margins=28, spacing=14)
        ol.addWidget(label('Text and colour', 'sectionTitle'))
        ol.addWidget(label('Text size', 'cardTitle'))
        self.font_slider, fr = self._slider(90, 160, 10, 'font_size_pct', '%')
        ol.addLayout(fr)
        ol.addWidget(label('Letter spacing', 'cardTitle'))
        self.spacing_slider, spacing_row = self._slider(0, 4, 1, 'letter_spacing_px', 'px')
        ol.addLayout(spacing_row)
        ol.addWidget(label('Colour', 'cardTitle'))
        self.color_combo = QComboBox()
        for text, value in [
            ('Standard', 'standard'), ('High contrast', 'high_contrast'),
            ('Warm reading', 'warm'), ('Cool blue', 'cool'),
        ]:
            self.color_combo.addItem(text, value)
        self.color_combo.setAccessibleName('Colour theme')
        self.color_combo.currentIndexChanged.connect(
            lambda _: self._change_option('color_profile', self.color_combo.currentData()))
        ol.addWidget(self.color_combo)
        ol.addSpacing(8)
        ol.addWidget(label('Sample', 'cardTitle'))
        self.visual_preview = VisualPreview()
        ol.addWidget(self.visual_preview)
        lay.addWidget(options)
        lay.addSpacing(16)
        self._photo_pair(lay, shots[1], shots[2], 280)

        tint, tl = card(margins=28, spacing=14)
        tl.addWidget(label('Optional tint', 'sectionTitle'))
        tl.addWidget(label(
            'A light colour wash on AccessShift windows only. Your desktop stays unchanged.',
            'bodyText', True,
        ))
        self.tint_color_combo = QComboBox()
        for text, value in [
            ('Soft navy', 'warm'), ('Cool blue', 'cool'), ('Soft mist', 'rose'),
        ]:
            self.tint_color_combo.addItem(text, value)
        self.tint_color_combo.setAccessibleName('AccessShift window tint colour')
        self.tint_color_combo.currentIndexChanged.connect(
            lambda _: self._change_option('tint_color', self.tint_color_combo.currentData()))
        tl.addWidget(self.tint_color_combo)
        tl.addWidget(label('How strong', 'cardTitle'))
        self.tint_slider, tint_row = self._slider(0, 20, 1, 'tint_opacity', '%')
        tl.addLayout(tint_row)
        self.tint_row = PreferenceRow(
            'Use tint',
            'Applies only to AccessShift and the Demo Lab window.',
        )
        self.tint_row.changed.connect(self._set_screen_tint)
        tl.addWidget(self.tint_row)
        self.tint_status = label('Window tint is off', 'bodyText')
        tl.addWidget(self.tint_status)
        lay.addWidget(tint)
        self._photo_band(lay, shots[3], 300)
        lay.addStretch()
        return page

    def _page_communication(self):
        page, lay = self._page(
            'Speech & text assistance',
            'Write a message and speak it aloud. Predictive suggestions are connected by Avneet’s module.',
        )
        shots = self._photos('speech')
        self._text_on_photo(
            lay, shots[0],
            'Speak what you write.',
            'Test a message here. Predictive text hooks in from the speech module.',
            height=420,
        )
        speak, spl = card(margins=28, spacing=14)
        spl.addWidget(label('Text-to-speech settings', 'sectionTitle'))
        self.speech_row = PreferenceRow('Enable communication support',
                                        'Allow supported speech and predictive-text functionality.')
        self.speech_row.changed.connect(lambda v: self._change_module('predictive_speech', v))
        spl.addWidget(self.speech_row)
        spl.addSpacing(8)
        spl.addWidget(label('Speaking speed', 'cardTitle'))
        self.speech_slider, srl = self._slider(100, 220, 10, 'speech_rate', 'wpm')
        spl.addLayout(srl)
        spl.addWidget(label('Test message', 'cardTitle'))
        self.speech_input = QLineEdit('Hello, I am using AccessShift to communicate.')
        self.speech_input.setAccessibleName('Message to speak')
        spl.addWidget(self.speech_input)
        speak_button = button('Speak message', 'primaryButton')
        speak_button.setMinimumHeight(48)
        speak_button.setMinimumWidth(200)
        speak_button.clicked.connect(self._speak)
        spl.addWidget(speak_button, alignment=Qt.AlignmentFlag.AlignLeft)
        lay.addWidget(speak)
        self._photo_pair(lay, shots[1], shots[2], 320)
        self._photo_band(lay, shots[3], 380)
        info, il = card(name='innerCard', margins=24, spacing=12)
        il.addWidget(label('Module ownership', 'cardTitle'))
        il.addWidget(label('Avneet owns the speech engine and predictive text. This page exposes the controls; '
                           'text-to-speech is available only if its Python backend is installed and working.',
                           'bodyText', True))
        lay.addWidget(info)
        self._photo_pair(lay, shots[4], shots[5], 300)
        self._text_on_photo(
            lay, shots[6],
            'Clear words, quiet room.',
            'Keep rate comfortable. Revisit this page whenever you need a quick speak test.',
            height=360,
        )
        self._photo_band(lay, shots[7], 340)
        lay.addStretch()
        return page

    def _set_screen_tint(self, enabled: bool) -> None:
        try:
            if enabled:
                self.tint_manager.update(color=self.prefs.tint_color, opacity=self.prefs.tint_opacity)
                self.tint_manager.enable()
            else:
                self.tint_manager.disable()
        except Exception as exc:
            self.tint_manager.disable()
            QMessageBox.warning(self, 'Window tint unavailable',
                                'The local window overlay could not be applied.\n\n' + str(exc))
        self.tint_row.set_value(self.tint_manager.active)
        self.tint_status.setText('Tint on · AccessShift and Demo Lab only.' if self.tint_manager.active
                                 else 'Window tint is off · other applications are unaffected.')

    def _apply_visual_preferences(self) -> None:
        apply_accessshift_appearance(self, self._base_qss, self.prefs.font_size_pct, self.prefs.color_profile)
        if hasattr(self, 'visual_preview'):
            self.visual_preview.set_preferences(self.prefs.font_size_pct, self.prefs.color_profile,
                                                self.prefs.letter_spacing_px)
        if hasattr(self, 'color_combo'):
            self.color_combo.blockSignals(True)
            self.color_combo.setCurrentIndex(max(0, self.color_combo.findData(self.prefs.color_profile)))
            self.color_combo.blockSignals(False)
        if hasattr(self, 'tint_color_combo'):
            self.tint_color_combo.blockSignals(True)
            self.tint_color_combo.setCurrentIndex(max(0, self.tint_color_combo.findData(self.prefs.tint_color)))
            self.tint_color_combo.blockSignals(False)
        self.tint_manager.update(color=self.prefs.tint_color, opacity=self.prefs.tint_opacity)
        if hasattr(self, 'tint_row'):
            self.tint_row.set_value(self.tint_manager.active)
        if hasattr(self, 'tint_status'):
            self.tint_status.setText('Tint on · AccessShift and Demo Lab only.' if self.tint_manager.active
                                     else 'Window tint is off · other applications are unaffected.')

    def closeEvent(self, event):
        self.tint_manager.disable()
        super().closeEvent(event)

    def _page_test(self):
        page, lay = self._page(
            'Try demos',
            'Practice SteadyHand here. Start HeadPoint from Home or the HeadPoint page.',
        )
        shots = self._photos('test')
        self._photo_band(lay, shots[0], 280)

        jump = QHBoxLayout()
        jump.setSpacing(12)
        head_btn = button('Calibrate HeadPoint', 'primaryButton')
        head_btn.setMinimumHeight(52)
        head_btn.clicked.connect(self._try_headpoint_calibrate)
        head_demo = button('Try HeadPoint demo', 'secondaryButton')
        head_demo.setMinimumHeight(52)
        head_demo.clicked.connect(self._try_headpoint_demo)
        jump.addWidget(head_btn, 1)
        jump.addWidget(head_demo, 1)
        lay.addLayout(jump)
        lay.addSpacing(16)

        test, tl = card(margins=28, spacing=16)
        tl.addWidget(label('SteadyHand practice', 'sectionTitle'))
        tl.addWidget(label(
            'Pick a mode, then start a short trial. Watch how SteadyHand helps shaky movement.',
            'bodyText',
            True,
        ))

        ctrl_row = QHBoxLayout()
        ctrl_row.setSpacing(12)
        self.test_mode_combo = QComboBox()
        for mode in TremorPlayground.MODES:
            self.test_mode_combo.addItem(mode)
        self.test_mode_combo.setCurrentIndex(3)
        self.test_mode_combo.currentIndexChanged.connect(self._on_test_mode_changed)
        ctrl_row.addWidget(self.test_mode_combo, 2)

        self.btn_start_trial = button('Start trial', 'primaryButton')
        self.btn_start_trial.setMinimumHeight(44)
        self.btn_start_trial.clicked.connect(self._start_trial)
        ctrl_row.addWidget(self.btn_start_trial)

        self.btn_abort_trial = button('Abort trial', 'secondaryButton')
        self.btn_abort_trial.setEnabled(False)
        self.btn_abort_trial.setMinimumHeight(44)
        self.btn_abort_trial.clicked.connect(self._abort_trial)
        ctrl_row.addWidget(self.btn_abort_trial)

        self.btn_export_results = button('Export JSON', 'secondaryButton')
        self.btn_export_results.setMinimumHeight(44)
        self.btn_export_results.clicked.connect(self._export_trial_results)
        ctrl_row.addWidget(self.btn_export_results)

        reset = button('Reset scores', 'secondaryButton')
        reset.setMinimumHeight(44)
        reset.clicked.connect(self._reset_test_scores)
        ctrl_row.addWidget(reset)
        tl.addLayout(ctrl_row)

        self.playground = TremorPlayground(
            self.steady,
            target_padding=16.0 * (self.prefs.target_size_pct / 100.0),
        )
        tl.addWidget(self.playground)
        self.test_score = label(
            'Mode: Smoothing + Target assistance  •  Status: Ready for trial',
            'cardTitle',
        )
        tl.addWidget(self.test_score)
        self.playground.metrics_changed.connect(self._update_test_score)
        self.playground.trial_progress.connect(self._on_trial_progress)
        self.playground.trial_completed.connect(self._on_trial_completed)

        self.simulation_row = PreferenceRow(
            'Simulate shaky movement',
            'Applies multi-frequency tremor inside this test only.',
        )
        self.simulation_row.set_value(True)
        self.simulation_row.changed.connect(self.playground.set_simulation)
        tl.addWidget(self.simulation_row)
        lay.addWidget(test)
        lay.addSpacing(16)

        hist_card, hl = card(margins=28, spacing=12)
        hl.addWidget(label('Your results', 'sectionTitle'))
        self.trial_history_label = label(
            'No trials yet. Choose a mode and press Start trial.',
            'bodyText',
            True,
        )
        hl.addWidget(self.trial_history_label)
        lay.addWidget(hist_card)
        self._photo_pair(lay, shots[1], shots[2], 260)
        lay.addStretch()
        return page

    def _slider(self, minimum, maximum, step, key, suffix):
        widget = QSlider(Qt.Orientation.Horizontal)
        widget.setRange(minimum, maximum)
        widget.setSingleStep(step)
        widget.setPageStep(step)
        widget.setAccessibleName(key.replace('_', ' '))
        widget.valueChanged.connect(lambda value, k=key: self._change_option(k, value))
        value_label = label('', 'pill')
        row = QHBoxLayout()
        row.addWidget(widget, 1)
        row.addWidget(value_label)
        self._sliders[key] = (widget, value_label, suffix)
        return widget, row

    def _navigate(self, key):
        if hasattr(self, 'playground') and self.playground.trial and not self.playground.trial.complete and key != 'test':
            self.playground.abort_trial()
            self._abort_trial()
        self.stack.setCurrentWidget(self._pages[key])
        for k, btn in self._nav.items():
            btn.setChecked(k == key)

    def _finish_setup(self):
        self.prefs.initial_setup_complete = True
        self._save()
        self._navigate('overview')

    def _apply_profile(self, profile_id):
        p = PROFILES[profile_id]
        if profile_id != 'custom':
            self.prefs.profile = profile_id
            for key in ('gaze_control', 'steady_hand', 'smart_interface', 'predictive_speech'):
                setattr(self.prefs, key, bool(p[key]))
        else:
            self.prefs.profile = 'custom'
        self._apply_preferences_to_engine()
        self._save()
        self._refresh()

    def _apply_preferences_to_engine(self):
        previous = self._syncing_engine
        self._syncing_engine = True
        try:
            self.engine.set_profile(self.prefs.profile)
            for key in ('gaze_control', 'steady_hand', 'smart_interface', 'predictive_speech'):
                self.engine.set_module(key, getattr(self.prefs, key))
        finally:
            self._syncing_engine = previous
        self.steady.strength = self.prefs.tremor_strength / 100.0
        self.steady.enabled = self.prefs.steady_hand and self.prefs.assistance_enabled

    def _on_external_modules_changed(self, flags):
        """Follow updates sent by other team members through AdaptiveEngine."""
        if self._syncing_engine:
            return
        self.prefs.profile = self.engine.profile.id
        for key in ('gaze_control', 'steady_hand', 'smart_interface', 'predictive_speech'):
            setattr(self.prefs, key, bool(getattr(flags, key)))
        self.steady.enabled = self.prefs.steady_hand and self.prefs.assistance_enabled
        self._save()
        self._refresh()

    def _change_module(self, key, value):
        setattr(self.prefs, key, bool(value))
        # A user can tweak a preset without losing its selected options.
        self.prefs.profile = 'custom'
        self._apply_preferences_to_engine()
        self._save()
        self._refresh()

    def _change_option(self, key, value):
        setattr(self.prefs, key, int(value) if isinstance(value, int) and not isinstance(value, bool) else value)
        if key == 'tremor_strength':
            self.steady.strength = self.prefs.tremor_strength / 100.0
        if key == 'target_size_pct' and hasattr(self, 'playground'):
            self.playground.set_target_padding(16.0 * (self.prefs.target_size_pct / 100.0))
        self._save()
        self._refresh()

    def _save(self):
        save_settings(self.prefs)
        self.preferences_changed.emit(self.prefs.as_dict())

    def _refresh(self):
        flags = ('gaze_control', 'steady_hand', 'smart_interface', 'predictive_speech')
        active = sum(bool(getattr(self.prefs, k)) for k in flags)
        name = PROFILES.get(self.prefs.profile, PROFILES['custom'])['label']
        self.overview_profile.setText('Your setup: ' + name)
        self.stat_modules.value.setText(f'{active} / 4')
        self.stat_profile.value.setText('Personal' if self.prefs.profile == 'custom' else 'Preset')
        for k, lbl in self.overview_module_labels.items():
            enabled = getattr(self.prefs, k)
            lbl.setText('On' if enabled else 'Off')
            cell = self._module_cells.get(k)
            if cell is None:
                continue
            if hasattr(cell, 'set_active'):
                cell.set_active(enabled)
            else:
                cell.setProperty('active', enabled)
                cell.style().unpolish(cell)
                cell.style().polish(cell)
        for k, btn in self._preset_buttons.items():
            btn.setChecked(k == self.prefs.profile)
        for k, row in self._toggle_rows.items():
            row.set_value(getattr(self.prefs, k))
        self.gaze_toggle.set_value(self.prefs.gaze_control)
        if hasattr(self, 'gaze_viewport'):
            self.gaze_viewport.set_tracking_active(bool(self.prefs.gaze_control))
        if hasattr(self, 'dwell_gauge'):
            self.dwell_gauge.set_dwell_ms(int(self.prefs.gaze_dwell_ms))
        if hasattr(self, 'dwell_band'):
            self.dwell_band.setText(dwell_band_label(int(self.prefs.gaze_dwell_ms)))
        self.steady_toggle.set_value(self.prefs.steady_hand)
        self.interface_toggle.set_value(self.prefs.smart_interface)
        self.speech_row.set_value(self.prefs.predictive_speech)
        self.simple_row.set_value(self.prefs.reduce_complexity)
        self.blink_row.set_value(self.prefs.blink_select)
        for k, (slider, text, suffix) in self._sliders.items():
            value = int(getattr(self.prefs, k))
            slider.blockSignals(True)
            slider.setValue(value)
            slider.blockSignals(False)
            text.setText(f'{value} {suffix}')
        self.footer_status.setText('✓  Settings saved on this device')
        self._apply_visual_preferences()

    def _on_gaze_toggle(self, value: bool) -> None:
        self._change_module('gaze_control', value)
        if hasattr(self, 'gaze_viewport'):
            self.gaze_viewport.set_tracking_active(bool(value))

    def _try_headpoint_calibrate(self) -> None:
        """Turn HeadPoint on if needed, then open calibration."""
        if hasattr(self, 'gaze_toggle'):
            self.gaze_toggle.set_value(True)
        self._on_gaze_toggle(True)
        self._request_calibration()

    def _try_headpoint_demo(self) -> None:
        """Start HeadPoint booking focus (calibrate if the camera is cold)."""
        if hasattr(self, 'gaze_toggle'):
            self.gaze_toggle.set_value(True)
        self._on_gaze_toggle(True)
        # Recalibrate when starting the demo so pointing lands on the big buttons.
        self._request_calibration()

    def _try_steady_demo(self) -> None:
        """Jump to the SteadyHand practice canvas with the module armed."""
        if hasattr(self, 'steady_toggle'):
            self.steady_toggle.set_value(True)
        self._change_module('steady_hand', True)
        self._navigate('test')

    def _on_dwell_preview(self, value: int) -> None:
        if hasattr(self, 'dwell_gauge'):
            self.dwell_gauge.set_dwell_ms(int(value))
        if hasattr(self, 'dwell_band'):
            self.dwell_band.setText(dwell_band_label(int(value)))

    def _request_calibration(self):
        self.calibration_requested.emit()
        QMessageBox.information(
            self, 'Gaze calibration integration',
            'The calibration screen is not connected to the webcam worker yet.\n\n'
            'Your teammate can connect a handler to MainWindow.calibration_requested '
            'and then display the live calibration widget.',
        )

    def _speak(self):
        msg = self.speech_input.text().strip()
        if not msg:
            QMessageBox.information(self, 'Speech', 'Enter a phrase to speak first.')
            return
        if not self.prefs.predictive_speech:
            QMessageBox.information(self, 'Speech', 'Enable communication support first.')
            return
        try:
            if self.speech is None:
                from accessshift.modules.speech.tts import SpeechEngine
                self.speech = SpeechEngine()
            if not self.speech.enabled:
                raise RuntimeError('The speech engine could not initialize on this device.')
            if callable(getattr(self.speech, 'set_rate', None)):
                self.speech.set_rate(self.prefs.speech_rate)
            elif getattr(self.speech, '_engine', None) is not None:
                self.speech._engine.setProperty('rate', self.prefs.speech_rate)
            self.speech.speak(msg)
        except Exception as exc:
            QMessageBox.warning(self, 'Speech unavailable', str(exc))

    def _on_test_mode_changed(self, index: int) -> None:
        self.playground.set_mode(index)
        self.test_score.setText(f'Mode: {self.playground.MODES[index]}  •  Status: Ready for trial')

    def _start_trial(self) -> None:
        self.playground.start_trial()
        self.test_mode_combo.setEnabled(False)
        self.btn_start_trial.setEnabled(False)
        self.btn_abort_trial.setEnabled(True)

    def _abort_trial(self) -> None:
        self.playground.abort_trial()
        self.test_mode_combo.setEnabled(True)
        self.btn_start_trial.setEnabled(True)
        self.btn_abort_trial.setEnabled(False)
        self.test_score.setText('Trial aborted. Ready to start again.')

    def _reset_test_scores(self) -> None:
        self.playground.reset_scores()
        self.test_score.setText('Scores reset.')

    def _on_trial_progress(self, summary: dict, expected: str | None) -> None:
        if expected is None:
            return
        lbl = LABELS.get(expected, expected)
        hits = summary['hits']
        misses = summary['misses']
        total = summary['interactions']
        acc = f"{summary['accuracy']:.0%}" if total > 0 else '—'
        elapsed = f"{summary['seconds']:.1f}s"
        self.test_score.setText(
            f'Target {hits + 1}/10: [{lbl}]  •  Hits: {hits}  •  Misses: {misses}  •  Accuracy: {acc}  •  Time: {elapsed}'
        )

    def _on_trial_completed(self, trial: Trial) -> None:
        self.test_mode_combo.setEnabled(True)
        self.btn_start_trial.setEnabled(True)
        self.btn_abort_trial.setEnabled(False)
        s = trial.summary()
        self.test_score.setText(
            f"Trial completed. Mode: {trial.mode}  •  Accuracy: {s['accuracy']:.0%}  •  Time: {s['seconds']:.1f}s"
        )
        self._refresh_trial_history()

    def _refresh_trial_history(self) -> None:
        if not self.playground.results:
            self.trial_history_label.setText('No completed trials yet.')
            return
        lines = []
        for i, t in enumerate(self.playground.results, 1):
            s = t.summary()
            lines.append(
                f"Trial #{i}  •  {s['mode']}: {s['accuracy']:.0%} accuracy  |  "
                f"{s['hits']} hits, {s['misses']} misses  |  {s['seconds']:.1f}s"
            )
        self.trial_history_label.setText('\n'.join(lines))

    def _export_trial_results(self) -> None:
        if not self.playground.results:
            QMessageBox.information(
                self,
                'Export Results',
                'No completed trials to export yet. Run at least one trial first.',
            )
            return
        default_name = f'steadyhand-results-{int(time.time())}.json'
        default_path = str(self.repo_root / default_name)
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            'Export Trial Results JSON',
            default_path,
            'JSON Files (*.json)',
        )
        if file_path:
            save_results(file_path, self.playground.results, extra=self.prefs.as_dict())
            QMessageBox.information(
                self,
                'Export Successful',
                f'Exported {len(self.playground.results)} trial records to:\n{file_path}',
            )

    def _update_test_score(self, hits, misses):
        n = hits + misses
        accuracy = f'{hits / n:.0%}' if n else '—'
        if not (self.playground.trial and not self.playground.trial.complete):
            self.test_score.setText(
                f'Free practice  •  Hits: {hits}  •  Misses: {misses}  •  Accuracy: {accuracy}'
            )
