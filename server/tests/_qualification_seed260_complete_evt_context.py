"""Qualify complete native eVt context and scoped seed restoration."""
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
        "EncounterAreaSeedProgramTests", module
    )
