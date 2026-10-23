"""Explicit warm-run imports for two new bounded scopes; never opens a catalog."""
import importlib
import unittest


IDS = (
    "test_recurring_modulox_strict_boss_delta.RecurringModuloxStrictBossDeltaTests."
    "test_two_strict_boss_sources_preserve_62_and_settle_authenticated_final_room_once",
    "test_environmental_archmonster_cadence_upgrade.EnvironmentalArchmonsterCadenceUpgradeTests."
    "test_61_public_cadences_preserve_59_and_both_existing_v1_birth_deadlines",
)


def qualify():
    for name in (
        "wakfu_server.objectives.environmental_modulox_contracts",
        "wakfu_server.objectives.environmental_recurring_storage",
        "test_recurring_modulox_strict_boss_delta",
        "test_environmental_archmonster_cadence_upgrade",
    ):
        importlib.reload(importlib.import_module(name))
    return unittest.defaultTestLoader.loadTestsFromNames(IDS)
