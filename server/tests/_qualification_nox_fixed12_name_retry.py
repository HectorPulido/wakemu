"""Retry a construction-only fixture failure with the same canonical checker."""
import sys


def qualify():
    api = sys.modules["_nox_loaded_implementation_checkpoint"]
    assert "_code" in api._function.__code__.co_names
    previous = sys.modules.get("test_nox_cube24_fixed12_joint")
    assert previous is None or not previous.retained_components
    return sys.modules["_private_nox_fixed12_staged_qualifier"].qualify()
