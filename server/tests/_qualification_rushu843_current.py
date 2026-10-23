"""Qualify the manifest-scoped removal operand after releasing prior checkpoint."""
import importlib
import unittest
from _qualification_resumed_scopes import _refresh_function


def qualify():
    om = importlib.import_module("test_ombrage_native_paid_clock")
    assert om.OMBRAGE_ACTUAL_CHECKPOINT is None
    helper = importlib.reload(
        importlib.import_module("wakfu_server.combat_encounter_area_seed_source")
    )
    assert hasattr(helper, "resolve_seed_program_selection")
    _refresh_function(
        "wakfu_server.combat_effect_runtime",
        "__call__",
        classname="NativeEffectRuntimeFactory",
        preserve_aliases=True,
    )
    factory = importlib.import_module("wakfu_server.combat_effect_runtime")
    groups = importlib.import_module("wakfu_server.combat_state_level_group")
    assert factory.native_state_group_level is groups.runtime_child_level
    module = importlib.reload(
        importlib.import_module("test_combat_encounter_area_seed_removal_selection")
    )
    return unittest.defaultTestLoader.loadTestsFromTestCase(
        module.SeedRemovalSelectionTests
    )


def actual():
    module = importlib.reload(
        importlib.import_module("test_rushu_native_party_phase_one")
    )
    return unittest.defaultTestLoader.loadTestsFromName(
        "RushuNativePartyPhaseOneTests.test_original_seed_program_initializes_qq_and_real_ap_pickup",
        module,
    )
