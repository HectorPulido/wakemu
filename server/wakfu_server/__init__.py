"""Python services for the isolated Wakfu experiment.

Area folders extend the package search path, retaining existing module names
and a single module identity for callers, private imports and patches.
"""
from pathlib import Path as _Path

_package = _Path(__file__).resolve().parent
__path__.extend(
    str(_package / area)
    for area in ("combat", "items", "maps", "storage", "characters")
)
