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


def test_squares_use_high_contrast_gaze_style(portal):
    from accessshift.ui import gaze_style

    g = GazeGridPanel(portal)
    g.refresh()
    assert all(gaze_style.TEXT in b.styleSheet() for b in g.visible_squares())
