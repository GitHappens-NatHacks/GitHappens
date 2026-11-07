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
    assert adaptive_dwell_ms(0) == 2000
    assert adaptive_dwell_ms(100) == 2300
    assert adaptive_dwell_ms(500) == 3500
    assert adaptive_dwell_ms(-100) == 2000
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


# --- grace period: a short glance away must not restart the ring ---

def test_brief_glance_away_keeps_progress():
    d = DwellSelector(1000, grace_ms=300)
    for t in range(0, 601, 50):
        d.update("a", t)
    state = d.update("b", 650)  # one jittery frame on a neighbour
    assert state.target == "a"  # still counting for "a"
    d.update(None, 700)
    fired = [d.update("a", t).fired for t in range(750, 1101, 50)]
    assert any(fired)


def test_long_look_away_switches_target():
    d = DwellSelector(1000, grace_ms=300)
    d.update("a", 0)
    d.update("a", 500)
    d.update("b", 600)
    state = d.update("b", 950)  # 350 ms on b: past the grace period
    assert state.target == "b" and state.progress == pytest.approx(0.0)
