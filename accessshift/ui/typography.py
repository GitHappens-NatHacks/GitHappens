"""Load AccessShift display/body faces from bundled font files."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QFontDatabase

_LOADED = False
DISPLAY_FAMILY = 'Alumni Sans'
BODY_FAMILY = 'Albert Sans'


def ensure_fonts(repo_root: Path) -> None:
    global _LOADED, DISPLAY_FAMILY, BODY_FAMILY
    if _LOADED:
        return
    fonts = Path(repo_root) / 'assets' / 'fonts'
    for name, attr in (('AlumniSans.ttf', 'DISPLAY_FAMILY'), ('AlbertSans.ttf', 'BODY_FAMILY')):
        path = fonts / name
        if not path.is_file():
            continue
        font_id = QFontDatabase.addApplicationFont(str(path))
        if font_id < 0:
            continue
        families = QFontDatabase.applicationFontFamilies(font_id)
        if families:
            if attr == 'DISPLAY_FAMILY':
                DISPLAY_FAMILY = families[0]
            else:
                BODY_FAMILY = families[0]
    _LOADED = True
