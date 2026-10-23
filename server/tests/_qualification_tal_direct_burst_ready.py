"""Reload only the corrected bounded actual Tal recipe."""
import importlib, unittest


def qualify():
    previous = importlib.import_module("test_talkasha_paid_native_rykaon")
    assert previous.TAL_ACTUAL_CHECKPOINT is None
    module = importlib.reload(previous)
    module.TAL_HOLD_ACTUAL_CHECKPOINT = False
    return unittest.defaultTestLoader.loadTestsFromName(
        "TalKashaPaidNativeRykaonTests.test_paid_cardinal_lights_and_native_phase_produce_eligible_rykaon_and_8148",
        module,
    )
