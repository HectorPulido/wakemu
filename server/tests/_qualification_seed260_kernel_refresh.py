"""Reload coherent new seed dataclass and setup functions for affected contracts."""
import importlib, unittest


def qualify():
    importlib.reload(
        importlib.import_module("wakfu_server.combat_encounter_area_seeds")
    )
    importlib.reload(
        importlib.import_module("wakfu_server.combat_rushu_encounter_setup")
    )
    importlib.reload(importlib.import_module("test_encounter_seed_programs"))
    importlib.reload(
        importlib.import_module("test_combat_encounter_area_seed_programs")
    )
    suite = unittest.TestSuite()
    suite.addTests(
        unittest.defaultTestLoader.loadTestsFromName(
            "test_encounter_seed_programs.EncounterSeedProgramTests.test_complete_native_program_inventory_and_reconstructed_level_are_frozen"
        )
    )
    module = importlib.import_module("test_combat_encounter_area_seed_programs")
    for cls in vars(module).values():
        if (
            isinstance(cls, type)
            and issubclass(cls, unittest.TestCase)
            and cls.__module__ == module.__name__
        ):
            suite.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(cls))
    return suite
