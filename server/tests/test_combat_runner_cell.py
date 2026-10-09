import unittest
from types import SimpleNamespace
from wakfu_server.combat_effect_dispatch import EffectInvocation
from wakfu_server.combat_trigger_value_modifier import NativeRunnerAmount
from wakfu_server.combat_runner_target import (
    bind_runner_target,
    runner_target_invocation,
)
from wakfu_server.combat_runner_cell import reflect_source_cell
from wakfu_server.combat_final_modifier import final_modifier_source


class RunnerCellTests(unittest.TestCase):
    def fixture(self, properties=frozenset()):
        invocation = EffectInvocation(10, 1, 7, 8, (2, 3, 0))
        runner = NativeRunnerAmount(11, 1, rng=lambda: 0, value=9)
        bind_runner_target(runner, invocation)
        source = SimpleNamespace(
            uid=11,
            effect_action_id=1,
            runner_modifier=runner,
            caster_id=7,
            target_id=8,
            cell=invocation.cell,
        )
        fight = SimpleNamespace(
            actors={
                7: SimpleNamespace(
                    id=7, position=(4, 5, 6), native_world_properties=properties
                )
            }
        )
        return invocation, runner, source, fight

    def test_reflection_changes_only_live_source_cell_and_is_not_reset_on_rebinding(
        self,
    ):
        original, runner, source, fight = self.fixture()
        reflection = EffectInvocation(
            76294, 1, 8, 7, (0, 0, 0), native_trigger_context={"uid": 11}
        )
        with final_modifier_source(source):
            self.assertTrue(reflect_source_cell(fight, reflection, None))
        bind_runner_target(runner, original)
        actual = runner_target_invocation(runner, original)
        self.assertEqual(actual.cell, (4, 5, 6))
        self.assertEqual((actual.caster_id, actual.target_id, runner.value), (7, 8, 9))

    def test_boss_guard_cancels_reflection_without_modifying_source(self):
        original, runner, source, fight = self.fixture(frozenset((43,)))
        with final_modifier_source(source):
            self.assertFalse(reflect_source_cell(fight, original, None))
        self.assertEqual(runner_target_invocation(runner, original).cell, original.cell)

    def test_missing_source_and_unaudited_runner_reject_explicit_trigger(self):
        original, runner, source, fight = self.fixture()
        reflection = EffectInvocation(
            76294, 1, 8, 7, (0, 0, 0), native_trigger_context={"uid": 11}
        )
        with self.assertRaisesRegex(ValueError, "source runner"):
            reflect_source_cell(fight, reflection, None)
        del runner.native_cell_binding
        with final_modifier_source(source), self.assertRaisesRegex(
            ValueError, "unaudited"
        ):
            reflect_source_cell(fight, reflection, None)


if __name__ == "__main__":
    unittest.main()
