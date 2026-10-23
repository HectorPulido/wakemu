"""Refresh the fixed native SP transmission and its sole new kernel contract."""
import importlib, unittest


def qualify():
    importlib.reload(
        importlib.import_module("wakfu_server.combat_encounter_area_seeds")
    )
    importlib.reload(
        importlib.import_module("wakfu_server.combat_rushu_encounter_setup")
    )
    module = importlib.reload(
        importlib.import_module("test_combat_encounter_area_seed_programs")
    )
    return unittest.defaultTestLoader.loadTestsFromName(
        "EncounterAreaSeedProgramTests.test_root_initial_level_uses_native_sp_transmission_without_fake_container",
        module,
    )
