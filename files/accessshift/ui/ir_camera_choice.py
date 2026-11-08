"""Discover IR in a subprocess; ask before any IR capture is opened."""
from __future__ import annotations
import importlib.util
import json
import sys
from PySide6.QtCore import QProcess, QSettings, QTimer
from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton, QMessageBox, QInputDialog

KEY = 'gaze/ir_camera_choice_v1'
DISCOVER = "import json, whircam; print(json.dumps([{'index':g['index'],'name':g['name']} for g in whircam.find_groups()]))"


def discover(parent=None):
    dialog = QDialog(parent)
    dialog.setWindowTitle('Checking for an infrared camera')
    layout = QVBoxLayout(dialog)
    layout.addWidget(QLabel('Checking camera sources. No camera preview is being opened.'))
    cancel = QPushButton('Keep regular webcam')
    layout.addWidget(cancel)
    cancel.clicked.connect(dialog.reject)
    proc = QProcess(dialog)
    timer = QTimer(dialog)
    timer.setSingleShot(True)
    timer.timeout.connect(dialog.reject)
    result = {'groups': [], 'error': ''}

    def finished(*args):
        timer.stop()
        try:
            if proc.exitCode() != 0:
                raise RuntimeError(bytes(proc.readAllStandardError()).decode(errors='replace')[-800:])
            output = bytes(proc.readAllStandardOutput()).decode(errors='replace')
            result['groups'] = json.loads(output.strip().splitlines()[-1])
        except Exception as exc:
            result['error'] = str(exc)
        dialog.accept()

    proc.finished.connect(finished)
    proc.errorOccurred.connect(lambda *_: dialog.reject())
    proc.start(sys.executable, ['-c', DISCOVER])
    timer.start(20000)
    dialog.exec()
    timer.stop()
    if proc.state() != QProcess.ProcessState.NotRunning:
        proc.kill()
        proc.waitForFinished(2000)
        return [], 'Discovery cancelled or timed out.'
    return result['groups'], result['error']


def choose_camera(parent=None, force=False):
    """Returns ('rgb', None) or ('ir', group name). Consent is remembered locally."""
    if sys.platform != 'win32':
        return 'rgb', None
    store = QSettings('GitHappens', 'AccessShift AI')
    remembered = store.value(KEY, '')
    if remembered and not force:
        try:
            data = json.loads(remembered)
            if data['kind'] in ('rgb', 'ir'):
                return data['kind'], data.get('group')
        except (ValueError, KeyError, TypeError):
            pass
    if force:
        choice, ok = QInputDialog.getItem(parent, 'Tracking camera', 'Choose an input:',
                                          ['Regular webcam', 'Detect infrared camera'], 0, False)
        if not ok:
            return None
        if choice == 'Regular webcam':
            store.setValue(KEY, json.dumps({'kind': 'rgb'}))
            return 'rgb', None
    if importlib.util.find_spec('whircam') is None:
        if force:
            QMessageBox.information(parent, 'Optional infrared support',
                'Install requirements-ir.txt in the same Python environment as AccessShift. '
                'Regular webcam tracking remains available.')
        return 'rgb', None
    groups, error = discover(parent)
    if not groups:
        QMessageBox.information(parent, 'Infrared camera unavailable',
            'No usable IR source was selected. Continuing with the regular webcam.\n' + error)
        return 'rgb', None
    box = QMessageBox(parent)
    box.setWindowTitle('Infrared camera detected')
    box.setText('Allow AccessShift to use an infrared camera for head tracking?')
    box.setInformativeText('Video is processed locally and is not recorded. Infrared tracking is experimental. '
                           'You can change cameras later; switching requires recalibration.')
    use = box.addButton('Use infrared', QMessageBox.ButtonRole.AcceptRole)
    regular = box.addButton('Keep regular webcam', QMessageBox.ButtonRole.RejectRole)
    box.setDefaultButton(regular)
    box.exec()
    selected = ('rgb', None)
    if box.clickedButton() is use:
        names = [g['name'] for g in groups]
        name, ok = (names[0], True) if len(names) == 1 else QInputDialog.getItem(
            parent, 'Infrared source', 'Select source (G14: Rts-DMFT-Group):', names, 0, False)
        if ok:
            selected = 'ir', name
    store.setValue(KEY, json.dumps({'kind': selected[0], 'group': selected[1]}))
    return selected
