"""Opt into preserving the actual scoped Tal runtime after one paid hit."""
import importlib
import unittest


def qualify():
    importlib.reload(
        importlib.import_module("wakfu_server.combat_fulmoon_talkasha_scenes")
    )
    module = importlib.reload(
        importlib.import_module("test_talkasha_paid_native_rykaon")
    )
    module.TAL_HOLD_ACTUAL_CHECKPOINT = True
    return unittest.defaultTestLoader.loadTestsFromName(
        "TalKashaPaidNativeRykaonTests.test_paid_melee_hit_preserves_actual_continuous_ray_checkpoint",
        module,
    )
