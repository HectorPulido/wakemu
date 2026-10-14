"""Registered native area criterion actor has a proven negative PLAYER kind."""
import unittest
from types import SimpleNamespace
from unittest.mock import patch


class AreaPlayerKindTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import test_combat_runtime_adapter as fixture

        fixture.ServerAdapterTests.setUpClass()

    def test_real_condition_adapter_marks_registered_area_as_nonplayer(self):
        import test_combat_runtime_adapter as fixture
        from wakfu_server.combat_effect_dispatch import EffectInvocation
        from wakfu_server.combat_conditions import evaluate_condition

        f = fixture.ServerAdapterTests()
        f.setUp()
        area = SimpleNamespace(
            native_running_effect_manager=False,
            native_fight_properties=frozenset(),
            state_ledger=None,
        )
        with patch(
            "wakfu_server.combat_state_managers.registered_area_pv", return_value=area
        ):
            context = f.adapter.condition(
                f.preview, {}, None, EffectInvocation(326382, 200, 7, 999, (1, 0, 0))
            )
        self.assertFalse(evaluate_condition('IsPlayer("target")', context))
        self.assertTrue(evaluate_condition('not IsPlayer("target")', context))
