"""Thread-based webcam and face mesh capture worker with zero Qt dependencies."""

from __future__ import annotations

import threading
from collections.abc import Callable

PREVIEW_WIDTH = 420


class GazeWorker:
    """Runs tracker open/read/close on a dedicated daemon thread."""

    def __init__(
        self,
        tracker_factory: Callable[[], object],
        preview: bool = False,
        on_sample: Callable[[dict], None] | None = None,
        on_error: Callable[[str], None] | None = None,
        on_finished: Callable[[], None] | None = None,
    ):
        self._tracker_factory = tracker_factory
        self.preview = preview
        self._on_sample = on_sample
        self._on_error = on_error
        self._on_finished = on_finished
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()
        self.tracker = None

    @property
    def running(self) -> bool:
        with self._lock:
            return self._thread is not None and self._thread.is_alive()

    def start(self) -> bool:
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return True
            self._stop_event.clear()
            self._thread = threading.Thread(
                target=self.run,
                name="gaze-capture-worker",
                daemon=True,
            )
            self._thread.start()
            return True

    def stop(self, timeout: float = 3.0) -> None:
        self._stop_event.set()
        with self._lock:
            thread = self._thread
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=timeout)
        with self._lock:
            if self._thread is thread and (thread is None or not thread.is_alive()):
                self._thread = None

    def run(self) -> None:
        tracker = None
        try:
            tracker = self._tracker_factory()
            self.tracker = tracker
            if not tracker.open():
                if self._on_error is not None:
                    self._on_error(
                        "Camera could not be opened. On macOS allow camera access in "
                        "System Settings > Privacy & Security > Camera."
                    )
                return
            while not self._stop_event.is_set():
                sample = tracker.read()
                if sample is None:
                    break
                frame = sample.pop("frame", None)
                if self.preview and frame is not None:
                    import cv2

                    h, w = frame.shape[:2]
                    sample["frame"] = cv2.resize(
                        frame,
                        (PREVIEW_WIDTH, max(1, h * PREVIEW_WIDTH // w)),
                    )
                if self._on_sample is not None:
                    self._on_sample(sample)
        except Exception as exc:
            if self._on_error is not None:
                self._on_error(f"Gaze tracking stopped: {exc}")
        finally:
            if tracker is not None:
                try:
                    tracker.close()
                except Exception:
                    pass
            if self._on_finished is not None:
                self._on_finished()
