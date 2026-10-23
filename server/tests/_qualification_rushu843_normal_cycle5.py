"""One changed normal lifecycle caller, retaining the admitted runtime implementation."""
import importlib
import sys
import unittest


def qualify():
    nox = sys.modules["test_nox_cube24_fixed12_joint"]
    assert len(nox.retained_components) == 1
    nox.verify_retained_component(nox.retained_components[0])
    module = importlib.reload(
        importlib.import_module("test_rushu_native_party_phase_one")
    )
    return unittest.defaultTestLoader.loadTestsFromName(
        "RushuNativePartyPhaseOneTests.test_normal_party_heals_and_rotates_native_nearest_recipient",
        module,
    )
