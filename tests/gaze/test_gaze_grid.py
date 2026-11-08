from pathlib import Path

import pytest

from accessshift.ui.gaze_grid import GazeGridPanel
from accessshift.ui.portal_view import PortalView

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def portal(qapp):
    p = PortalView(ROOT / "assets" / "portal")
    p.set_accessible(True)
    return p


def labels(grid):
    return [b.text() for b in grid.visible_squares()]


def cells(grid):
    layout = grid.grid_layout()
    out = []
    for b in grid.visible_squares():
        r, c, rs, cs = layout.getItemPosition(layout.indexOf(b))
        out.append((r, c, cs))
    return out


def test_first_step_shows_its_options_and_title(portal):
    g = GazeGridPanel(portal)
    g.refresh()
    assert labels(g) == ["Myself", "Someone I care for"]
    assert cells(g) == [(0, 0, 1), (0, 1, 1)]  # 2 options: left | right
    assert "Who is booking?" in g.heading()


def test_choosing_a_square_clicks_the_portal_and_moves_on(portal):
    g = GazeGridPanel(portal)
    g.refresh()
    g.visible_squares()[0].click()  # "Myself"
    assert labels(g) == ["Check-up", "Follow-up", "New concern", "Back"]
    assert cells(g) == [(0, 0, 1), (0, 1, 1), (1, 0, 1), (1, 1, 1)]  # 2 x 2
    assert "What kind of visit?" in g.heading()


def test_three_options_last_spans_bottom_row(qapp):
    from PySide6.QtWidgets import QPushButton, QVBoxLayout, QWidget

    src = QWidget()
    lay = QVBoxLayout(src)
    for t in ("A", "B", "C"):
        lay.addWidget(QPushButton(t))
    g = GazeGridPanel(src)
    g.refresh()
    assert cells(g) == [(0, 0, 1), (0, 1, 1), (1, 0, 2)]


def test_full_booking_through_the_grid(portal):
    g = GazeGridPanel(portal)
    g.refresh()
    for choice in ("Myself", "Check-up", "Tomorrow 10:00"):
        next(b for b in g.visible_squares() if b.text() == choice).click()
    assert labels(g) == ["Book appointment", "Back"]
    assert "Confirm appointment" in g.heading()
    assert "Tomorrow 10:00" in g.heading()


def test_book_appointment_shows_booking_confirmation(portal, qapp, monkeypatch):
    from PySide6.QtWidgets import QDialog, QLabel

    import accessshift.ui.portal_view as portal_mod

    seen = []

    class FakeDialog(QDialog):
        def __init__(self, who, visit, when, parent=None, auto_close_ms=5000):
            super().__init__(parent)
            seen.append({"who": who, "visit": visit, "when": when})
            layout_labels = QLabel(f"You're booked!\n{visit}\nfor {who}\n{when}")
            layout_labels.setParent(self)

        def exec(self):
            return QDialog.DialogCode.Accepted

    monkeypatch.setattr(portal_mod, "BookingConfirmationDialog", FakeDialog)

    g = GazeGridPanel(portal)
    g.refresh()
    for choice in ("Myself", "Check-up", "Tomorrow 10:00"):
        next(b for b in g.visible_squares() if b.text() == choice).click()
    next(b for b in g.visible_squares() if b.text() == "Book appointment").click()
    assert seen == [{"who": "Myself", "visit": "Check-up", "when": "Tomorrow 10:00"}]
    assert labels(g) == ["Myself", "Someone I care for"]  # reset to start


def test_squares_use_high_contrast_gaze_style(portal):
    from accessshift.ui import gaze_style

    g = GazeGridPanel(portal)
    g.refresh()
    assert all(gaze_style.TEXT in b.styleSheet() for b in g.visible_squares())
