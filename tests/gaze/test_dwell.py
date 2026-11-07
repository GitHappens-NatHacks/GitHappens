import pytest

from accessshift.modules.gaze.dwell import DwellSelector, adaptive_dwell_ms, min_target_px


def test_fires_after_dwell():
    d = DwellSelector(1000)
    assert d.update("a", 0).progress == 0
    assert d.update("a", 500).progress == pytest.approx(0.5)
    state = d.update("a", 1000)
    assert state.fired and state.progress == 1.0 and state.target == "a"


def test_fires_once_until_reentry():
    d = DwellSelector(1000)
    d.update("a", 0)
    d.update("a", 1000)
    assert not d.update("a", 3000).fired
    d.update("b", 3100)
    d.update("a", 3200)
    assert d.update("a", 4200).fired


def test_target_change_resets_progress():
    d = DwellSelector(1000)
    d.update("a", 0)
    d.update("a", 900)
    assert d.update("b", 950).progress == 0


def test_none_resets():
    d = DwellSelector(1000)
    d.update("a", 0)
    d.update("a", 900)
    state = d.update(None, 950)
    assert state.target is None and state.progress == 0 and not state.fired
    assert d.update("a", 1000).progress == 0  # timer restarted


def test_reset_rearms_same_target():
    d = DwellSelector(1000)
    d.update("a", 0)
    d.update("a", 1000)
    d.reset()
    d.update("a", 1100)
    assert d.update("a", 2100).fired


def test_adaptive_values():
    assert adaptive_dwell_ms(0) == 800 and adaptive_dwell_ms(500) == 2000
    assert adaptive_dwell_ms(-100) == 600
    assert adaptive_dwell_ms(100) == 1200
    assert min_target_px(10) == 64 and min_target_px(50) == 100
    assert min_target_px(50.2) == 101


def test_consume_after_blink_blocks_dwell_on_same_target():
    d = DwellSelector(1000)
    d.update("a", 0)
    d.update("a", 300)
    d.consume()  # selected by blink
    assert not d.update("a", 2000).fired
    d.update("b", 2100)
    d.update("a", 2200)
    assert d.update("a", 3200).fired
