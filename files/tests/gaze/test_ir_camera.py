import types
import pytest
from accessshift.modules.gaze.ir_camera import IRCapture
from accessshift.ui import ir_camera_choice as choice
from accessshift.modules.gaze.controller import GazeController

class FakeCamera:
    illuminated = True
    def __init__(self, **kwargs):
        self.kwargs=kwargs
        self.released=False
    def read(self, timeout):
        return True, 'frame'
    def release(self):
        self.released=True


def test_ir_adapter_reads_and_releases_once():
    c=IRCapture('Rts-DMFT-Group',factory=FakeCamera)
    backend=c._cap
    assert backend.kwargs['group']=='Rts-DMFT-Group'
    assert c.read()==(True,'frame')
    c.release();c.release()
    assert backend.released and not c.isOpened()


def test_ambient_frames_are_not_used():
    c=IRCapture(factory=FakeCamera)
    c._cap.illuminated=False
    assert c.read()==(False,None)
    c.release()


def test_no_usable_frames_times_out(monkeypatch):
    c=IRCapture(factory=FakeCamera)
    c._cap.illuminated=False
    c._last_frame=0
    monkeypatch.setattr('accessshift.modules.gaze.ir_camera.time.monotonic',lambda:20)
    with pytest.raises(RuntimeError,match='no usable'):
        c.read()
    c.release()


def test_non_windows_never_discovers(monkeypatch):
    monkeypatch.setattr(choice.sys,'platform','darwin')
    monkeypatch.setattr(choice,'discover',lambda *_:pytest.fail('Must not discover'))
    assert choice.choose_camera()==('rgb',None)


def test_remembered_webcam_never_discovers(monkeypatch,qapp):
    monkeypatch.setattr(choice.sys,'platform','win32')
    monkeypatch.setattr(choice,'QSettings',lambda *_:types.SimpleNamespace(value=lambda *_:'{"kind":"rgb"}'))
    monkeypatch.setattr(choice,'discover',lambda *_:pytest.fail('Must not discover'))
    assert choice.choose_camera()==('rgb',None)


def test_remembered_ir_returns_selection_without_opening(monkeypatch,qapp):
    monkeypatch.setattr(choice.sys,'platform','win32')
    monkeypatch.setattr(choice,'QSettings',lambda *_:types.SimpleNamespace(value=lambda *_:'{"kind":"ir","group":"Rts-DMFT-Group"}'))
    assert choice.choose_camera()==('ir','Rts-DMFT-Group')


def test_reset_camera_clears_calibration(qapp):
    c=GazeController()
    c.error_px=12
    c.reset_camera_calibration()
    assert c.error_px is None
    assert not c.calibration.is_fitted
