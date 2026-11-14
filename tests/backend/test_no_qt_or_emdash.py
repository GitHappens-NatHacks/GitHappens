import ast
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[2] / "backend"
FORBIDDEN_PREFIXES = ("PySide6", "PyQt5", "PyQt6", "shiboken6")


def test_backend_has_zero_qt_imports():
    py_files = list(BACKEND_ROOT.rglob("*.py"))
    assert py_files, "Expected Python modules under backend/"
    for path in py_files:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert not alias.name.startswith(FORBIDDEN_PREFIXES), (
                        f"Forbidden Qt import {alias.name!r} in {path}"
                    )
            elif isinstance(node, ast.ImportFrom) and node.module:
                assert not node.module.startswith(FORBIDDEN_PREFIXES), (
                    f"Forbidden Qt import {node.module!r} in {path}"
                )


def test_backend_and_new_tests_contain_no_emdashes():
    roots = [BACKEND_ROOT, Path(__file__).resolve().parent]
    for root in roots:
        for path in root.rglob("*.py"):
            content = path.read_text(encoding="utf-8")
            assert "\u2014" not in content, f"Emdash found in {path}"
