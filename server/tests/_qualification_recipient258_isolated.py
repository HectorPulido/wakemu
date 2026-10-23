"""Qualify the isolated recipient policy while retaining admitted role hooks."""
import importlib
import unittest
from _qualification_resumed_scopes import _refresh_function


class RestoringSuite(unittest.TestSuite):
    def run(self, result, debug=False):
        try:
            return super().run(result, debug)
        finally:
            function, code, defaults, kwdefaults = self.saved
            function.__code__ = code
            function.__defaults__ = defaults
            function.__kwdefaults__ = kwdefaults
            assert (
                "freeze_encounter_recipient_binding_policy"
                not in function.__code__.co_names
            )


def qualify():
    roles = importlib.import_module("wakfu_server.combat_encounter_roles")
    function = roles.bind_roles
    saved = (
        function,
        function.__code__,
        function.__defaults__,
        function.__kwdefaults__,
    )
    assert "freeze_encounter_recipient_binding_policy" not in function.__code__.co_names
    importlib.reload(
        importlib.import_module("wakfu_server.combat_encounter_recipient_binding")
    )
    for name in ("__init__", "candidate_invocations"):
        _refresh_function(
            "wakfu_server.combat_effect_resolver",
            name,
            classname="NativeEffectResolver",
            preserve_aliases=True,
        )
    _refresh_function(
        "wakfu_server.combat_encounter_roles", "bind_roles", preserve_aliases=True
    )
    importlib.reload(importlib.import_module("test_ogrest_native_recipient_binding"))
    suite = RestoringSuite()
    suite.saved = saved
    for name in (
        "test_ogrest_native_recipient_binding.OgrestNativeRecipientBindingTests",
        "test_combat_effect_resolver.NativeResolverTests.test_transmitted_rebound_point_recipient_keeps_identity",
        "test_combat_effect_resolver.NativeResolverTests.test_preselected_recipient_is_not_reselected_as_caster_or_area",
    ):
        suite.addTests(unittest.defaultTestLoader.loadTestsFromName(name))
    return suite


def qualify_failed():
    suite = qualify()
    suite._tests = [
        test
        for test in suite
        if test.id().endswith(
            ".test_four_native_elements_keep_boss_marker_and_actual_resistance"
        )
    ]
    assert suite.countTestCases() == 1
    return suite
