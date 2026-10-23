"""Qualify isolated owned START reconstruction without adopting unadmitted hooks."""
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
            assert "freeze_owned_start_binding" not in function.__code__.co_names


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
    importlib.reload(
        importlib.import_module("wakfu_server.combat_encounter_owned_start_binding")
    )
    _refresh_function(
        "wakfu_server.combat_event_replay",
        "__call__",
        classname="NativeEventReplay",
        preserve_aliases=True,
    )
    _refresh_function(
        "wakfu_server.combat_encounter_roles", "bind_roles", preserve_aliases=True
    )
    importlib.reload(importlib.import_module("test_nox_owned_start_binding"))
    importlib.reload(
        importlib.import_module("test_ordinary_encounter_policy_admission")
    )
    suite = ScopedSuite()
    suite.saved = saved
    for name in (
        "test_nox_owned_start_binding.NoxOwnedStartBindingTests",
        "test_nox_owned_start_binding.NoxOwnedStartReplayHookTests.test_real_replay_binds_clone_and_children_only_and_failed_preview_is_discardable",
        "test_ordinary_encounter_policy_admission.OrdinaryEncounterPolicyAdmissionTests.test_prepare_scene_binds_ordinary_ombrage_policy_and_pins_absence_on_retry",
    ):
        suite.addTests(unittest.defaultTestLoader.loadTestsFromName(name))
    return unittest.TestSuite([suite])
