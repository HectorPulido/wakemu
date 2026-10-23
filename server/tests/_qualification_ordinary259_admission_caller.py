"""Qualify the single ordinary admission consumer of the isolated259 hook."""
import importlib, unittest
from _qualification_resumed_scopes import _refresh_function
from _qualification_nox259_isolated_contracts import ScopedSuite


def qualify():
    roles = importlib.import_module("wakfu_server.combat_encounter_roles")
    function = roles.bind_roles
    saved = (
        function,
        function.__code__,
        function.__defaults__,
        function.__kwdefaults__,
    )
    assert "freeze_owned_start_binding" not in function.__code__.co_names
    _refresh_function(
        "wakfu_server.combat_encounter_roles", "bind_roles", preserve_aliases=True
    )
    importlib.reload(
        importlib.import_module("test_ordinary_encounter_policy_admission")
    )
    suite = ScopedSuite()
    suite.saved = saved
    suite.addTests(
        unittest.defaultTestLoader.loadTestsFromName(
            "test_ordinary_encounter_policy_admission.OrdinaryEncounterPolicyAdmissionTests.test_prepare_scene_binds_ordinary_ombrage_policy_and_pins_absence_on_retry"
        )
    )
    return unittest.TestSuite([suite])
