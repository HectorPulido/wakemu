"""Refresh the ordinary arena admission function and its two affected contracts."""
import importlib, unittest
from _qualification_resumed_scopes import _refresh_function


def qualify():
    _refresh_function(
        "wakfu_server.combat_encounter_scene_layout",
        "_apply_team_roles",
        preserve_aliases=True,
    )
    for name in (
        "test_ordinary_encounter_policy_admission",
        "test_combat_encounter_scene_layout",
    ):
        importlib.reload(importlib.import_module(name))
    suite = unittest.TestSuite()
    for name in (
        "test_ordinary_encounter_policy_admission.OrdinaryEncounterPolicyAdmissionTests.test_prepare_scene_binds_ordinary_ombrage_policy_and_pins_absence_on_retry",
        "test_combat_encounter_scene_layout.ScenePlacementTests.test_normal_encounter_preserves_arena_without_loading_reconstruction",
    ):
        suite.addTests(unittest.defaultTestLoader.loadTestsFromName(name))
    return suite
