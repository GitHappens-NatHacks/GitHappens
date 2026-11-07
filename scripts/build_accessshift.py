"""Cross-platform PyInstaller build for AccessShift (run on EACH target OS).

From the GitHappens repo after installing dependencies:
    python scripts/build_accessshift.py

PyInstaller does not cross-compile; build macOS on Mac and Windows on Windows.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    sep = os.pathsep
    command = [
        sys.executable, '-m', 'PyInstaller', '--noconfirm', '--windowed',
        '--name', 'AccessShiftAI', '--paths', str(ROOT),
        '--add-data', f'{ROOT / "accessshift/ui/control_center_styles.qss"}{sep}accessshift/ui',
        '--add-data', f'{ROOT / "assets"}{sep}assets',
        str(ROOT / 'accessshift/__main__.py'),
    ]
    print('Building AccessShift on', sys.platform)
    subprocess.run(command, cwd=ROOT, check=True)
    print('Build complete. Look inside dist/AccessShiftAI')


if __name__ == '__main__':
    main()
