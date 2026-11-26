"""Task metrics, trial logging, and multi-band Welch PSD telemetry for SteadyHand."""

from __future__ import annotations

import json
import math
import time
from collections import deque
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable, Sequence

import numpy as np
from scipy import signal as scipy_signal


@dataclass(frozen=True)
class Click:
    seconds: float
    expected: str
    selected: str | None
    x: float
    y: float
    hit: bool


class Trial:
    """Tracks a sequence of target selection tasks within a designated mode."""

    def __init__(
        self,
        mode: str,
        sequence: Sequence[str],
        clock: Callable[[], float] = time.perf_counter,
    ):
        if not sequence:
            raise ValueError("A trial needs at least one target in its sequence")
        self.mode = str(mode)
        self.sequence = tuple(sequence)
        self.clock = clock
        self.started = clock()
        self.finished: float | None = None
        self.index = 0
        self.clicks: list[Click] = []

    @property
    def expected(self) -> str | None:
        return None if self.complete else self.sequence[self.index]

    @property
    def complete(self) -> bool:
        return self.index >= len(self.sequence)

    def record(self, selected: str | None, x: float, y: float) -> bool:
        if self.complete:
            return False
        now = self.clock()
        expected = self.expected
        hit = (selected is not None) and (selected == expected)
        self.clicks.append(Click(now - self.started, str(expected), selected, float(x), float(y), hit))
        if hit:
            self.index += 1
            if self.complete:
                self.finished = now
        return hit

    def summary(self) -> dict[str, Any]:
        hits = sum(1 for c in self.clicks if c.hit)
        count = len(self.clicks)
        elapsed = (self.finished if self.finished is not None else self.clock()) - self.started
        return {
            "mode": self.mode,
            "completed": self.complete,
            "hits": hits,
            "misses": count - hits,
            "interactions": count,
            "accuracy": (hits / count) if count > 0 else 0.0,
            "seconds": elapsed,
        }

    def export(self) -> dict[str, Any]:
        return {
            **self.summary(),
            "sequence": list(self.sequence),
            "clicks": [asdict(c) for c in self.clicks],
        }


def save_results(path: str | Path, trials: Sequence[Trial], extra: dict[str, Any] | None = None) -> None:
    """Save trial metrics to a JSON file, optionally attaching active application settings."""
    payload: dict[str, Any] | list[dict[str, Any]]
    if extra is not None:
        payload = {
            "timestamp": time.time(),
            "meta": extra,
            "trials": [t.export() for t in trials],
        }
    else:
        payload = [t.export() for t in trials]

    target_path = Path(path)
    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _bandpass_rms(values_x: np.ndarray, values_y: np.ndarray, fs: float, low_hz: float, high_hz: float) -> float:
    """Compute 2D RMS tremor displacement (px) in [low_hz, high_hz] via rFFT bandpass."""
    n = len(values_x)
    if n < 16:
        return 0.0
    freqs = np.fft.rfftfreq(n, d=1.0 / fs)
    mask = (freqs >= low_hz) & (freqs <= high_hz)
    if not np.any(mask):
        return 0.0
    spec_x = np.fft.rfft(values_x)
    spec_y = np.fft.rfft(values_y)
    spec_x[~mask] = 0.0
    spec_y[~mask] = 0.0
    bp_x = np.fft.irfft(spec_x, n=n)
    bp_y = np.fft.irfft(spec_y, n=n)
    return float(np.sqrt(np.mean(bp_x * bp_x + bp_y * bp_y)))


class MotorTelemetry:
    """Four-second raw displacement spectrum (resting 4-6 Hz & action 6-12 Hz), updated twice per second."""

    # Logical CSS/Cocoa pixels per millimeter (~96 PPI / 25.4 mm/inch)
    PX_PER_MM_BASE = 96.0 / 25.4

    def __init__(self, max_history: int = 1000):
        self.samples: deque[tuple[float, float, float]] = deque(maxlen=512)
        self.filtered_samples: deque[tuple[float, float, float]] = deque(maxlen=512)
        self.history: deque[dict[str, Any]] = deque(maxlen=max(10, int(max_history)))
        self.latest: dict[str, Any] | None = None
        self.last_valid_score: float = 100.0
        self.spastic_drags_prevented = 0
        self.slip_clicks_rescued = 0
        self.double_clicks_blocked = 0
        self.scroll_jitters_filtered = 0
        self.total_clicks = 0
        self._path_distance = 0.0

    def reset_window(self) -> None:
        self.samples.clear()
        self.filtered_samples.clear()
        self.latest = None
        self._path_distance = 0.0

    def sample(
        self,
        x: float,
        y: float,
        now: float,
        simulated: bool = False,
        *,
        dpi_scale: float = 1.0,
        filtered_pos: tuple[float, float] | None = None,
    ) -> None:
        if self.samples and now <= self.samples[-1][0]:
            return
        if self.samples:
            prev_t, prev_x, prev_y = self.samples[-1]
            dt = now - prev_t
            step_dist = math.hypot(x - prev_x, y - prev_y)
            # Only reset on genuine idle gaps (>1.5s) or monitor teleport jumps (>500px).
            if dt > 1.5 or step_dist > 500.0:
                self.reset_window()
            else:
                self._path_distance += step_dist

        self.samples.append((now, x, y))
        if filtered_pos is not None:
            self.filtered_samples.append((now, float(filtered_pos[0]), float(filtered_pos[1])))

        while self.samples and now - self.samples[0][0] > 4.0:
            old = self.samples.popleft()
            if self.samples:
                self._path_distance = max(
                    0.0,
                    self._path_distance - math.hypot(self.samples[0][1] - old[1], self.samples[0][2] - old[2]),
                )
        while self.filtered_samples and now - self.filtered_samples[0][0] > 4.0:
            self.filtered_samples.popleft()

        span = now - self.samples[0][0]
        if len(self.samples) < 60 or span < 2.5:
            return
        if self._path_distance < 10.0:
            return
        if self.latest and now - self.latest["sample_time"] < 0.5:
            return

        times, xs, ys = np.asarray(self.samples).T
        fs = 60.0
        grid = np.arange(times[0], times[-1], 1.0 / fs)
        if len(grid) < 32:
            return

        # Welch PSD with Hann tapering reduces spectral leakage across 4-12 Hz motor tremor bands.
        nperseg = min(len(grid), 240)
        hz = None
        power = None
        interp_axes: list[np.ndarray] = []
        for axis in (xs, ys):
            values = np.interp(grid, times, axis)
            values -= np.linspace(values[0], values[-1], len(grid))
            values -= values.mean()
            interp_axes.append(values)
            freqs, psd = scipy_signal.welch(
                values,
                fs=fs,
                window="hann",
                nperseg=nperseg,
                noverlap=nperseg // 2,
                detrend=False,
            )
            hz = freqs
            power = psd if power is None else (power + psd)

        assert hz is not None and power is not None
        broad_tremor_band = (hz >= 4.0) & (hz <= 12.0)
        resting_band = (hz >= 4.0) & (hz < 6.0)
        action_band = (hz >= 6.0) & (hz <= 12.0)
        parkinson_band = (hz >= 4.0) & (hz <= 7.0)
        total = float(power[(hz >= 0.5) & (hz <= 15.0)].sum())

        if total > 1e-6:
            tremor_index = float(100.0 * power[broad_tremor_band].sum() / total)
            resting_pct = float(100.0 * power[resting_band].sum() / total)
            action_pct = float(100.0 * power[action_band].sum() / total)
            parkinson_pct = float(100.0 * power[parkinson_band].sum() / total)
        else:
            tremor_index = resting_pct = action_pct = parkinson_pct = 0.0

        dominant = (
            float(hz[broad_tremor_band][power[broad_tremor_band].argmax()])
            if tremor_index >= 10.0 and np.any(broad_tremor_band)
            else None
        )

        rms_px = _bandpass_rms(interp_axes[0], interp_axes[1], fs, 4.0, 12.0)
        px_per_mm = self.PX_PER_MM_BASE * max(1.0, float(dpi_scale))
        rms_mm = rms_px / px_per_mm

        filtered_rms_px = rms_px
        if len(self.filtered_samples) >= 32:
            ftimes, fxs, fys = np.asarray(self.filtered_samples).T
            f_interp_x = np.interp(grid, ftimes, fxs)
            f_interp_y = np.interp(grid, ftimes, fys)
            f_interp_x -= np.linspace(f_interp_x[0], f_interp_x[-1], len(grid))
            f_interp_y -= np.linspace(f_interp_y[0], f_interp_y[-1], len(grid))
            f_interp_x -= f_interp_x.mean()
            f_interp_y -= f_interp_y.mean()
            filtered_rms_px = _bandpass_rms(f_interp_x, f_interp_y, fs, 4.0, 12.0)

        suppression_ratio = (
            max(0.0, min(1.0, 1.0 - (filtered_rms_px / rms_px)))
            if rms_px > 0.25
            else 0.0
        )

        if tremor_index >= 50.0:
            severity = "elevated"
        elif tremor_index >= 30.0:
            severity = "moderate"
        elif tremor_index >= 12.0:
            severity = "mild"
        else:
            severity = "minimal"

        self.latest = {
            "timestamp": time.time(),
            "sample_time": now,
            "tremor_index": round(tremor_index, 2),
            "resting_band_pct": round(resting_pct, 2),
            "action_band_pct": round(action_pct, 2),
            "parkinson_band_pct": round(parkinson_pct, 2),
            "dominant_hz": dominant,
            "rms_amplitude_px": round(rms_px, 2),
            "rms_amplitude_mm": round(rms_mm, 2),
            "filtered_rms_px": round(filtered_rms_px, 2),
            "suppression_ratio": round(suppression_ratio, 3),
            "tremor_severity": severity,
            "medication_state_estimate": "OFF" if tremor_index >= 50.0 else "ON",
            "simulated": simulated,
        }
        self.history.append(self.latest)

    def export(self, path: str | Path) -> None:
        import csv

        rows = list(self.history)
        with Path(path).open("w", newline="", encoding="utf-8") as stream:
            if str(path).lower().endswith(".csv"):
                fields = (
                    "timestamp",
                    "sample_time",
                    "tremor_index",
                    "resting_band_pct",
                    "action_band_pct",
                    "dominant_hz",
                    "rms_amplitude_px",
                    "rms_amplitude_mm",
                    "tremor_severity",
                    "medication_state_estimate",
                    "simulated",
                )
                writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
                writer.writeheader()
                writer.writerows(rows)
            else:
                json.dump(rows, stream, indent=2)
