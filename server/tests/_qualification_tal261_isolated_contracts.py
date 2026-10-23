"""Qualify admitted-scope candidates without adopting their admission hook."""
import importlib, unittest
from _qualification_resumed_scopes import _refresh_function


class ScopedSuite(unittest.TestSuite):
    def run(self, result, debug=False):
        try:
            return super().run(result, debug)
        finally:
            function, code, defaults, kwdefaults = self.saved
            function.__code__ = code
            function.__defaults__ = defaults
            function.__kwdefaults__ = kwdefaults
            assert "freeze_event_population_policy" not in function.__code__.co_names


def qualify():
    roles = importlib.import_module("wakfu_server.combat_encounter_roles")
    function = roles.bind_roles
    saved = (
        function,
        function.__code__,
        function.__defaults__,
        function.__kwdefaults__,
    )
    assert "freeze_event_population_policy" not in function.__code__.co_names
    importlib.reload(
        importlib.import_module("wakfu_server.combat_encounter_event_population")
    )
    _refresh_function(
        "wakfu_server.combat_effect_runtime",
        "__call__",
        classname="NativeEffectRuntimeFactory",
        preserve_aliases=True,
    )
    _refresh_function(
        "wakfu_server.combat_encounter_roles", "bind_roles", preserve_aliases=True
    )
    for name in (
        "test_tal_event_population",
        "test_ordinary_encounter_policy_admission",
    ):
        importlib.reload(importlib.import_module(name))
    suite = ScopedSuite()
    suite.saved = saved
    for name in (
        "test_tal_event_population.TalEventPopulationTests",
        "test_ordinary_encounter_policy_admission.OrdinaryEncounterPolicyAdmissionTests.test_prepare_scene_binds_ordinary_ombrage_policy_and_pins_absence_on_retry",
    ):
        suite.addTests(unittest.defaultTestLoader.loadTestsFromName(name))
    return unittest.TestSuite([suite])
