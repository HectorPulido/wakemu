"""Stable compatibility entry; implementation lives in wakfu_ai.planning.planner."""
import importlib.util
from pathlib import Path
import sys

if "wakfu_ai" not in sys.modules:
    directory = Path(__file__).resolve().parent / "wakfu_ai"
    spec = importlib.util.spec_from_file_location(
        "wakfu_ai",
        directory / "__init__.py",
        submodule_search_locations=[str(directory)],
    )
    package = importlib.util.module_from_spec(spec)
    sys.modules["wakfu_ai"] = package
    spec.loader.exec_module(package)

from wakfu_ai.planning.planner import decide, validate, legal_movements


def __getattr__(name):
    from importlib import import_module

    return getattr(import_module("wakfu_ai.planning.planner"), name)
