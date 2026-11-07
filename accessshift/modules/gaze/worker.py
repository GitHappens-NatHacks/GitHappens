"""Runs the webcam + face mesh loop off the UI thread."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QObject, Signal, Slot


class GazeWorker(QObject):
    sample = Signal(dict)
    error = Signal(str)
    finished = Signal()

    def __init__(self, tracker_factory: Callable[[], object], preview: bool = False):
        super().__init__()
        self._tracker_factory = tracker_factory
        self.preview = preview  # keep the camera frame in samples (large; off by default)
        self._stop = False
        self.tracker = None  # set once run() has created it

    def stop(self) -> None:
        # Called from the UI thread; run() checks it every frame.
        self._stop = True

    @Slot()
    def run(self) -> None:
        tracker = None
        try:
            tracker = self.tracker = self._tracker_factory()
            if not tracker.open():
                self.error.emit(
                    "Camera could not be opened. On macOS allow camera access in "
                    "System Settings > Privacy & Security > Camera."
                )
                return
            while not self._stop:
                s = tracker.read()  # blocks until the next camera frame (~30 fps)
                if s is None:
                    break
                if not self.preview:
                    s.pop("frame", None)
                self.sample.emit(s)
        except Exception as exc:  # camera/mediapipe failures must not kill the app silently
            self.error.emit(f"Gaze tracking stopped: {exc}")
        finally:
            if tracker is not None:
                tracker.close()
            self.finished.emit()
