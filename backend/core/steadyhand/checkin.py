"""Standardized 15-second guided motor check-in scoring (hold stability + target tap accuracy)."""

from __future__ import annotations

import math
from typing import Any

from backend.core.steadyhand.metrics import MotorTelemetry


def evaluate_motor_checkin(
    *,
    hold_samples: list[dict[str, float]],
    target_x: float,
    target_y: float,
    taps: list[dict[str, float]] | None = None,
    tap_hit_radius_px: float = 28.0,
    pixels_per_mm: float | None = None,
    context_tag: str = "routine",
    notes: str = "",
) -> dict[str, Any]:
    """Compute standardized postural hold and kinetic tap metrics for a guided check-in."""
    px_per_mm = float(pixels_per_mm) if pixels_per_mm and pixels_per_mm > 0 else MotorTelemetry.PX_PER_MM_BASE
    taps_list = list(taps or [])

    if len(hold_samples) < 5:
        raise ValueError("At least 5 hold samples are required to score a motor check-in.")

    # Sort chronologically to guard against out-of-order client payloads
    ordered = sorted(hold_samples, key=lambda s: float(s.get("t", 0.0)))
    t0 = float(ordered[0].get("t", 0.0))
    t_end = float(ordered[-1].get("t", t0))
    duration_sec = max(0.0, round(t_end - t0, 2))

    # 1. Radial sway from target center
    sq_dists: list[float] = []
    for sample in ordered:
        dx = float(sample["x"]) - float(target_x)
        dy = float(sample["y"]) - float(target_y)
        sq_dists.append(dx * dx + dy * dy)

    hold_rms_px = math.sqrt(sum(sq_dists) / len(sq_dists))
    hold_rms_mm = hold_rms_px / max(1.0, px_per_mm)

    # 2. Spectral Welch PSD analysis (4-6 Hz resting band vs 6-12 Hz action band)
    telemetry = MotorTelemetry(max_history=10)
    for idx, sample in enumerate(ordered):
        ts = float(sample.get("t", idx / 60.0))
        telemetry.sample(float(sample["x"]), float(sample["y"]), ts, simulated=False)
    latest_fft = telemetry.latest

    if latest_fft is not None:
        hold_dominant_hz = latest_fft.get("dominant_hz")
        hold_resting_band_pct = float(latest_fft.get("resting_band_pct", 0.0))
        hold_action_band_pct = float(latest_fft.get("action_band_pct", 0.0))
        hold_tremor_index = float(latest_fft.get("tremor_index", 0.0))
        spectral_score = float(latest_fft.get("stability_score", 100.0))
    else:
        hold_dominant_hz = None
        hold_resting_band_pct = 0.0
        hold_action_band_pct = 0.0
        hold_tremor_index = round(min(100.0, hold_rms_mm * 14.0), 2)
        spectral_score = max(0.0, min(100.0, 100.0 - hold_tremor_index))

    # Combine radial target-hold accuracy (0 mm = 100, 10 mm RMS = 0) with spectral steadiness
    radial_score = max(0.0, min(100.0, 100.0 - (hold_rms_mm / 10.0) * 100.0))
    hold_stability_score = round(0.6 * radial_score + 0.4 * spectral_score, 2)

    # 3. Kinetic target tap metrics
    tap_count = len(taps_list)
    if tap_count > 0:
        errors: list[float] = []
        reactions: list[float] = []
        hits = 0
        radius = max(4.0, float(tap_hit_radius_px))
        for tap in taps_list:
            dx = float(tap["click_x"]) - float(tap["target_x"])
            dy = float(tap["click_y"]) - float(tap["target_y"])
            err = math.hypot(dx, dy)
            errors.append(err)
            if err <= radius:
                hits += 1
            if "reaction_ms" in tap and tap["reaction_ms"] is not None:
                reactions.append(max(0.0, float(tap["reaction_ms"])))
        tap_accuracy_pct = round((hits / tap_count) * 100.0, 2)
        tap_mean_error_px = round(sum(errors) / tap_count, 2)
        tap_mean_reaction_ms = round(sum(reactions) / len(reactions), 1) if reactions else 0.0
        tap_precision_score = max(0.0, min(100.0, 100.0 - (tap_mean_error_px / (radius * 2.0)) * 100.0))
        tap_component = 0.6 * tap_accuracy_pct + 0.4 * tap_precision_score
        overall_score = round(0.65 * hold_stability_score + 0.35 * tap_component, 2)
    else:
        tap_accuracy_pct = None
        tap_mean_error_px = None
        tap_mean_reaction_ms = None
        overall_score = hold_stability_score

    return {
        "context_tag": str(context_tag or "routine").strip()[:40],
        "duration_sec": duration_sec,
        "overall_score": overall_score,
        "hold_stability_score": hold_stability_score,
        "hold_rms_px": round(hold_rms_px, 2),
        "hold_rms_mm": round(hold_rms_mm, 3),
        "hold_dominant_hz": round(float(hold_dominant_hz), 2) if hold_dominant_hz is not None else None,
        "hold_resting_band_pct": round(hold_resting_band_pct, 2),
        "hold_action_band_pct": round(hold_action_band_pct, 2),
        "hold_tremor_index": round(hold_tremor_index, 2),
        "tap_count": tap_count,
        "tap_accuracy_pct": tap_accuracy_pct,
        "tap_mean_error_px": tap_mean_error_px,
        "tap_mean_reaction_ms": tap_mean_reaction_ms,
        "notes": str(notes or "").strip()[:400],
    }
