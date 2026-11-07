"""Healthcare appointment portal: complex vs accessible layouts."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from accessshift.modules.smartinterface.modes import PortalMode


class PortalView(QWidget):
    def __init__(self, portal_assets: Path):
        super().__init__()
        self.portal_assets = portal_assets
        self.mode = PortalMode.COMPLEX
        self._stack = QStackedWidget()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._stack)

        self._complex = self._build_complex()
        self._accessible = self._build_accessible()
        self._stack.addWidget(self._complex)
        self._stack.addWidget(self._accessible)

    def set_accessible(self, enabled: bool) -> None:
        self.mode = PortalMode.ACCESSIBLE if enabled else PortalMode.COMPLEX
        self._stack.setCurrentIndex(1 if enabled else 0)

    def toggle_mode(self) -> None:
        self.set_accessible(self.mode != PortalMode.ACCESSIBLE)

    def _build_complex(self) -> QWidget:
        page = QWidget()
        outer = QHBoxLayout(page)

        left = QVBoxLayout()
        left.addWidget(QLabel("Quick links"))
        for text in (
            "Billing statements",
            "Insurance FAQ (PDF)",
            "Parking map",
            "Research trials",
            "Gift shop hours",
        ):
            left.addWidget(QLabel(f"• {text}"))
        notice = QLabel("Seasonal flu clinic — register separately")
        notice.setStyleSheet("background:#fff4cc; padding:6px; border:1px dashed #c9a227;")
        left.addWidget(notice)
        left.addStretch(1)
        outer.addLayout(left, 1)

        center = QVBoxLayout()
        title = QLabel("Schedule an encounter")
        title.setStyleSheet("font-size:18px; font-weight:700;")
        center.addWidget(title)
        blurb = QLabel(
            "Complete all fields. Referral codes are required for specialty visits "
            "unless waived by administrative review."
        )
        blurb.setWordWrap(True)
        blurb.setStyleSheet("color:#5c6b7a; font-size:12px;")
        center.addWidget(blurb)

        identity = QGroupBox("Patient identifiers")
        form = QFormLayout(identity)
        for label in ("Legal last name", "Legal first name", "MRN / chart #", "DOB", "Pharmacy NPI"):
            form.addRow(label, QLineEdit())
        center.addWidget(identity)

        visit = QGroupBox("Visit configuration")
        vform = QFormLayout(visit)
        dept = QComboBox()
        dept.addItems(["Select…", "Primary care", "Cardiology", "Neurology", "Physiatry"])
        provider = QComboBox()
        provider.addItems(["Select…", "Dr. Okonkwo", "Dr. Singh", "NP Alvarez"])
        vform.addRow("Department", dept)
        vform.addRow("Provider", provider)
        vform.addRow("Reason", QTextEdit())
        vform.addRow(QCheckBox("I reviewed the 14-page visit policy"))
        vform.addRow(QCheckBox("Allow SMS reminders"))
        center.addWidget(visit)

        slots = QGroupBox("Available increments")
        grid = QGridLayout(slots)
        times = [
            "8:05",
            "8:12",
            "8:19",
            "8:27",
            "9:03",
            "9:11",
            "9:18",
            "9:26",
            "10:04",
            "10:15",
            "10:22",
            "10:41",
        ]
        for i, t in enumerate(times):
            btn = QPushButton(t)
            btn.setFixedSize(48, 22)
            btn.setStyleSheet("font-size:10px;")
            grid.addWidget(btn, i // 6, i % 6)
        center.addWidget(slots)

        actions = QHBoxLayout()
        actions.addStretch(1)
        actions.addWidget(QPushButton("Save draft"))
        submit = QPushButton("Submit request")
        submit.setFixedHeight(22)
        submit.setStyleSheet("font-size:10px; background:#0f6a5a; color:white;")
        actions.addWidget(submit)
        center.addLayout(actions)
        outer.addLayout(center, 3)

        right = QVBoxLayout()
        right.addWidget(QLabel("Notices"))
        tip = QLabel(
            "Forms expire after 12 minutes of inactivity. Incomplete referrals are auto-rejected."
        )
        tip.setWordWrap(True)
        tip.setStyleSheet("font-size:10px; color:#5c6b7a;")
        right.addWidget(tip)
        tiny = QPushButton("Download forms pack")
        tiny.setStyleSheet("font-size:10px;")
        right.addWidget(tiny)
        right.addStretch(1)
        outer.addLayout(right, 1)
        return page

    def _build_accessible(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(12)

        steps = QLabel("1. Who  →  2. Visit type  →  3. Time  →  4. Confirm")
        steps.setStyleSheet("font-size:14px; font-weight:600; color:#0f6a5a;")
        layout.addWidget(steps)

        self._acc_stack = QStackedWidget()
        layout.addWidget(self._acc_stack, 1)

        who = QWidget()
        who_l = QVBoxLayout(who)
        who_l.addWidget(self._big_title("Who is booking?"))
        who_group = QButtonGroup(who)
        for label in ("Myself", "Someone I care for"):
            btn = QPushButton(label)
            btn.setMinimumHeight(64)
            btn.setStyleSheet(self._big_btn_css())
            who_group.addButton(btn)
            btn.clicked.connect(lambda _=False, s=1: self._acc_stack.setCurrentIndex(s))
            who_l.addWidget(btn)
        who_l.addStretch(1)
        self._acc_stack.addWidget(who)

        visit = QWidget()
        visit_l = QVBoxLayout(visit)
        visit_l.addWidget(self._big_title("What kind of visit?"))
        for label in ("Check-up", "Follow-up", "New concern"):
            btn = QPushButton(label)
            btn.setMinimumHeight(64)
            btn.setStyleSheet(self._big_btn_css())
            btn.clicked.connect(lambda _=False, s=2: self._acc_stack.setCurrentIndex(s))
            visit_l.addWidget(btn)
        back = QPushButton("Back")
        back.setMinimumHeight(52)
        back.clicked.connect(lambda: self._acc_stack.setCurrentIndex(0))
        visit_l.addWidget(back)
        visit_l.addStretch(1)
        self._acc_stack.addWidget(visit)

        time_page = QWidget()
        time_l = QVBoxLayout(time_page)
        time_l.addWidget(self._big_title("Pick a time"))
        for label in ("Tomorrow 10:00", "Tomorrow 14:00", "Friday 11:30"):
            btn = QPushButton(label)
            btn.setMinimumHeight(64)
            btn.setStyleSheet(self._big_btn_css())
            btn.clicked.connect(lambda _=False, s=3: self._acc_stack.setCurrentIndex(s))
            time_l.addWidget(btn)
        back2 = QPushButton("Back")
        back2.setMinimumHeight(52)
        back2.clicked.connect(lambda: self._acc_stack.setCurrentIndex(1))
        time_l.addWidget(back2)
        time_l.addStretch(1)
        self._acc_stack.addWidget(time_page)

        confirm = QWidget()
        conf_l = QVBoxLayout(confirm)
        conf_l.addWidget(self._big_title("Confirm appointment"))
        conf_l.addWidget(QLabel("Review your choices, then book."))
        book = QPushButton("Book appointment")
        book.setMinimumHeight(64)
        book.setStyleSheet(self._big_btn_css())
        conf_l.addWidget(book)
        back3 = QPushButton("Back")
        back3.setMinimumHeight(52)
        back3.clicked.connect(lambda: self._acc_stack.setCurrentIndex(2))
        conf_l.addWidget(back3)
        conf_l.addStretch(1)
        self._acc_stack.addWidget(confirm)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(page)
        wrapper = QWidget()
        wrap_l = QVBoxLayout(wrapper)
        wrap_l.setContentsMargins(0, 0, 0, 0)
        wrap_l.addWidget(scroll)
        return wrapper

    @staticmethod
    def _big_title(text: str) -> QLabel:
        label = QLabel(text)
        label.setStyleSheet("font-size:22px; font-weight:700;")
        return label

    @staticmethod
    def _big_btn_css() -> str:
        return (
            "QPushButton { font-size:18px; font-weight:650; text-align:left; padding:12px; "
            "border:2px solid #1f4d43; border-radius:12px; background:#e7f6f1; }"
            "QPushButton:hover { background:#d2efe7; }"
        )
