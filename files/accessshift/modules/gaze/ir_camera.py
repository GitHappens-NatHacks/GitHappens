"""Optional Windows IR capture. No capture is opened during discovery/import."""
from __future__ import annotations
import sys
import time


class IRCapture:
    def __init__(self, group=0, factory=None):
        self._cap = None
        if factory is None:
            if sys.platform != 'win32':
                raise RuntimeError('Infrared capture is available on Windows only.')
            try:
                from whircam import IRCam
            except ImportError as exc:
                raise RuntimeError('Install requirements-ir.txt in this app environment.') from exc
            factory = IRCam
        self._cap = factory(group=group, format_output='bgr', timeout=8.0)
        self._last_frame = time.monotonic()

    def isOpened(self):
        return self._cap is not None

    def read(self):
        if self._cap is None:
            return False, None
        ok, frame = self._cap.read(timeout=0.25)
        if ok and frame is not None:
            # The public WHIRCAM illumination property is best-effort metadata.
            # Unknown metadata is accepted; explicitly ambient frames are skipped.
            if self._cap.illuminated is not False:
                self._last_frame = time.monotonic()
                return True, frame
        if time.monotonic() - self._last_frame > 10:
            raise RuntimeError('IR camera returned no usable illuminated frames for 10 seconds. '
                               'Choose Camera → Regular webcam to recover.')
        return False, None

    def release(self):
        cap, self._cap = self._cap, None
        if cap is not None:
            cap.release()
