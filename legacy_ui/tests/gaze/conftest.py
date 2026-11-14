import os

# Qt tests run headless: no window appears and no display is needed.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402


@pytest.fixture(scope="session")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture(autouse=True)
def no_real_pointing_chooser(monkeypatch):
    """The Head/Eye chooser is a blocking popup. Tests answer it with the current mode.

    The real chooser stays reachable as GazeCalibrationDialog._real_choose_source.
    """
    from accessshift.ui import gaze_calibration_dialog as dialog_mod

    cls = dialog_mod.GazeCalibrationDialog
    if not hasattr(cls, "_real_choose_source"):
        cls._real_choose_source = staticmethod(cls.choose_source)
    monkeypatch.setattr(
        cls, "choose_source", staticmethod(lambda current="head", parent=None, palette=None: current)
    )
