"""Reload only private recipe helpers and preserve their suite-finalization scope."""
import importlib, unittest


def qualify():
    tal = importlib.import_module("test_talkasha_paid_native_rykaon")
    assert tal.TAL_ACTUAL_CHECKPOINT is None
    importlib.reload(importlib.import_module("tools.ombrage_live_phase_handoff"))
    helper = importlib.reload(
        importlib.import_module("_qualification_ombrage40_retained_actual")
    )
    return unittest.TestSuite([helper.qualify()])
