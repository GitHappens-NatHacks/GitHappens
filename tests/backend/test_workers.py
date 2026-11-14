import threading

from backend.core.gaze.calibration import GazeCalibration
from backend.core.gaze.controller import (
    EXIT_CLOSE_MS,
    GazeController,
    GazeTarget,
    ScreenRect,
)
from backend.core.gaze.worker import GazeWorker
from backend.core.steadyhand.worker import SteadyHandWorker


def test_steadyhand_worker_fft_and_anti_drag():
    worker = SteadyHandWorker()
    worker.configure(
        enabled=True,
        strength=1.1,
        simulate_tremor=True,
        tremor_intensity=85,
        anti_drag=True,
    )
    worker.controller.new_tremor_pattern(seed=7)

    # Feed 4+ seconds of samples at 60 Hz to populate the FFT window.
    for i in range(280):
        worker.process_sample(400.0, 300.0, timestamp=i / 60.0)

    snap = worker.snapshot()
    assert snap["stabilization_active"] is True
    assert snap["tremor_hz"] is not None
    assert 4.0 <= snap["tremor_hz"] <= 7.0
    assert snap["tremor_index"] > 30.0
    assert 0.0 <= snap["stability_score"] <= 100.0

    rec = worker.consume_latest_fft_record()
    assert rec is not None
    assert worker.consume_latest_fft_record() is None

    # Test anti-drag rescue when jitter happens during a mouse press/release.
    worker.configure(simulate_tremor=False)
    worker.process_sample(100.0, 100.0, timestamp=10.0, pressed=True)
    worker.process_sample(114.0, 102.0, timestamp=10.05)
    worker.process_sample(102.0, 112.0, timestamp=10.10)
    after_release = worker.process_sample(104.0, 105.0, timestamp=10.15, pressed=False)
    assert after_release["spastic_drags_prevented"] >= 1


def test_steadyhand_worker_thread_lifecycle():
    worker = SteadyHandWorker(tick_hz=60.0)
    worker.configure(enabled=True, simulate_tremor=True, tremor_intensity=60)
    assert worker.start() is True
    assert worker.running is True
    worker.stop(timeout=2.0)
    assert worker.running is False


def test_gaze_worker_thread_with_mock_tracker():
    samples = []
    done = threading.Event()

    class FakeTracker:
        def __init__(self):
            self.closed = False
            self._count = 0

        def open(self):
            return True

        def read(self):
            self._count += 1
            if self._count > 3:
                return None
            return {
                "camera_ok": True,
                "face": True,
                "ts_ms": self._count * 33,
                "feature": (0.5, 0.0),
                "head": (0.0, 0.2),
                "ear": 0.3,
                "blink": False,
                "closed_ms": 0,
            }

        def close(self):
            self.closed = True

    tracker = FakeTracker()
    worker = GazeWorker(
        lambda: tracker,
        on_sample=samples.append,
        on_finished=done.set,
    )
    worker.start()
    assert done.wait(timeout=2.0)
    worker.stop()
    assert len(samples) == 3
    assert tracker.closed is True


def test_gaze_controller_dwell_blink_and_exit():
    selected = []
    exited = []
    target = GazeTarget(id="book-btn", x=100, y=100, width=120, height=80)

    ctrl = GazeController(
        screen_rect=ScreenRect(0, 0, 1000, 800),
        on_selected=selected.append,
        on_exit_requested=lambda: exited.append(True),
    )
    ctrl.set_source("eyes")
    ctrl.set_targets([target])
    ctrl.set_dwell_ms(600)

    pts = [(x, y) for x in (0, 500, 1000) for y in (0, 400, 800)]
    cal = GazeCalibration()
    cal.fit(pts, pts)
    ctrl.set_calibration(cal, error_px=25.0)

    # Dwell over target from 0 ms to 700 ms -> triggers selection once.
    for ts in (0, 200, 400, 650):
        ctrl.process(
            {
                "camera_ok": True,
                "face": True,
                "ts_ms": ts,
                "feature": (150.0, 140.0),
                "ear": 0.31,
                "blink": False,
                "closed_ms": 0,
            }
        )
    assert [t.id for t in selected] == ["book-btn"]

    # Hold eyes closed past EXIT_CLOSE_MS -> triggers exit callback.
    ctrl.process(
        {
            "camera_ok": True,
            "face": True,
            "ts_ms": 1000,
            "feature": (150.0, 140.0),
            "ear": 0.1,
            "blink": False,
            "closed_ms": EXIT_CLOSE_MS,
        }
    )
    assert exited == [True]
