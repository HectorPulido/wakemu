"""Load one staged paid Nox case using the canonical v2 checker."""
import importlib.util
import sys
from pathlib import Path


def qualify():
    key = "_nox_loaded_implementation_checkpoint"
    assert key not in sys.modules, "Never reuse or renew an existing admitted checker"
    spec = importlib.util.spec_from_file_location(
        key, ".runtime/tools/loaded_implementation_checkpoint.py"
    )
    api = importlib.util.module_from_spec(spec)
    sys.modules[key] = api
    spec.loader.exec_module(api)
    assert "_code" in api._function.__code__.co_names
    name = "_private_nox_fixed12_staged_qualifier"
    path = Path(
        ".runtime/staging/nox-cube24-fixed12-joint/qualify_nox_cube24_fixed12.py"
    )
    spec = importlib.util.spec_from_file_location(name, path)
    helper = importlib.util.module_from_spec(spec)
    sys.modules[name] = helper
    spec.loader.exec_module(helper)
    return helper.qualify()
