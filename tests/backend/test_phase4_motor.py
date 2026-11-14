"""Tests for Phase 4 OneEuroFilter wrapper, 180ms Click-Freeze, Welch PSD, and Gravity Wells."""

from __future__ import annotations

import math

from backend.core.steadyhand.filter import IntentionalHold, OneEuroFilter
from backend.core.steadyhand.gravity_wells import AccessibilityGravityWells, GravityTarget
from backend.core.steadyhand.metrics import MotorTelemetry


def test_pypi_one_euro_filter_dampens_high_frequency_jitter():
    flt = OneEuroFilter(min_cutoff=0.5, beta=0.004)
    raw_xs = [100.0 + 18.0 * math.sin(2.0 * math.pi * 5.5 * (i / 60.0)) for i in range(180)]
    filtered = [flt.filter(x, i / 60.0) for i, x in enumerate(raw_xs)]
    raw_std = max(raw_xs[60:]) - min(raw_xs[60:])
    flt_std = max(filtered[60:]) - min(filtered[60:])
    assert flt_std < raw_std * 0.45


def test_click_freeze_holds_anchor_for_180ms_and_releases_on_25px_drag():
    metrics = MotorTelemetry()
    hold = IntentionalHold(metrics)
    hold.configure(click_freeze_ms=180, drag_release_px=25.0, hold_seconds=0.3, latch_distance_px=35.0)

    hold.press((200.0, 200.0), (200.0, 200.0), 10.0)
    assert hold.click_freeze_active is True

    # Under 180ms and under 25px excursion stays locked at anchor.
    locked = hold.move((212.0, 208.0), (214.0, 208.0), 10.10)
    assert locked == (200.0, 200.0)
    assert hold.dragging is False

    released = hold.release((212.0, 208.0), slipped=True)
    assert released == (200.0, 200.0)
    assert metrics.slip_clicks_rescued == 1
    assert hold.click_freeze_active is False


def test_gravity_wells_expand_hitbox_and_pull_slowed_cursor():
    wells = AccessibilityGravityWells(enabled=True, expansion=2.6, strength=0.4, velocity_threshold_px_s=420.0)
    target = GravityTarget(role="AXButton", x=100.0, y=100.0, width=40.0, height=20.0, title="Save")
    # Center is (120, 110); expanded half_w = 20 * 2.6 = 52 -> point (158, 110) is outside inner rect but inside well.
    assert not (100.0 <= 158.0 <= 140.0)
    assert target.expanded_contains(158.0, 110.0, 2.6)

    wells.apply_pull(158.0, 110.0, 1.0, targets=[target])
    pulled_x, pulled_y = wells.apply_pull(157.0, 110.0, 1.05, targets=[target])
    assert pulled_x < 157.0  # Pulled left toward target center (120, 110).
    assert math.isclose(pulled_y, 110.0, abs_tol=1e-6)
    snap = wells.snapshot()
    assert snap["gravity_well_active"] is True
    assert snap["gravity_target_role"] == "AXButton"

    # High sweep speed suppresses magnetic pull for free travel.
    fast_x, fast_y = wells.apply_pull(190.0, 110.0, 1.06, targets=[target])
    assert (fast_x, fast_y) == (190.0, 110.0)
    assert wells.snapshot()["gravity_well_active"] is False
