import unittest
from types import SimpleNamespace
from wakfu_server.combat_effect_dispatch import EffectInvocation
from wakfu_server.combat_reflect_runner import NativeReflectRunnerHandler
from wakfu_server.combat_trigger_value_modifier import NativeRunnerAmount
from wakfu_server.combat_runner_target import (
    bind_runner_target,
    runner_target_invocation,
)
from wakfu_server.combat_final_modifier import final_modifier_source
from wakfu_server.combat_stat_handler import StatExecutionContext, NativeStatHandler


class ReflectRunnerTests(unittest.TestCase):
    def fixture(self, *, boss=False):
        actor = SimpleNamespace(
            id=7,
            position=(4, 5, 6),
            native_world_properties=frozenset((43,)) if boss else frozenset(),
        )
        fight = SimpleNamespace(
            id=1, phase="active", actors={7: actor}, owned_stat_effects={}
        )
        original = EffectInvocation(10, 1, 7, None, (1, 2, 0))
        runner = NativeRunnerAmount(11, 1, rng=lambda: 0, value=42)
        bind_runner_target(runner, original)
        source = SimpleNamespace(
            uid=11,
            effect_action_id=1,
            caster_id=7,
            target_id=None,
            cell=original.cell,
            runner_modifier=runner,
        )
        packets, phases = [], []
        handler = NativeReflectRunnerHandler(
            fight,
            packets,
            action_id=1,
            allocate_uid=lambda: 99,
            context=lambda *args: StatExecutionContext(
                True, True, None, True, b"", None
            ),
            rng=lambda: 0,
            authority=None,
        )
        handler.event_lifecycle = SimpleNamespace(
            phase=lambda *args, **kwargs: phases.append(kwargs["channel"]),
            register_applied=lambda *args: None,
        )
        effect = {
            "effect_class": 309,
            "parameters": [],
            "target_masks": [[] for _ in range(7)],
        }
        invocation = EffectInvocation(
            76294, 200, 7, 7, (0, 0, 0), native_trigger_context={"uid": 11}
        )
        return (
            fight,
            packets,
            phases,
            handler,
            effect,
            invocation,
            source,
            runner,
            original,
        )

    def test_server_reflection_mutates_cell_and_removal_preserves_source(self):
        (
            fight,
            packets,
            phases,
            handler,
            effect,
            invocation,
            source,
            runner,
            original,
        ) = self.fixture()
        with final_modifier_source(source):
            self.assertTrue(
                handler(effect, {}, handler.prepare(effect, {}, invocation))
            )
        self.assertEqual(runner_target_invocation(runner, original).cell, (4, 5, 6))
        self.assertEqual(
            (runner.value, runner_target_invocation(runner, original).target_id),
            (42, None),
        )
        self.assertEqual(phases, [1, 2, 3, 4])
        stat = NativeStatHandler(
            fight,
            packets,
            {"effects": {}},
            action_id=1,
            allocate_uid=lambda: 100,
            context=lambda *args: None,
        )
        stat.remove(99)
        self.assertEqual(packets[-1][0], 13560)
        self.assertEqual(runner_target_invocation(runner, original).cell, (4, 5, 6))
        self.assertFalse(fight.owned_stat_effects)

    def test_boss_cancels_only_reflection_and_cleans_prepared_owner(self):
        (
            fight,
            packets,
            phases,
            handler,
            effect,
            invocation,
            source,
            runner,
            original,
        ) = self.fixture(boss=True)
        with final_modifier_source(source):
            self.assertFalse(
                handler(effect, {}, handler.prepare(effect, {}, invocation))
            )
        self.assertEqual(runner_target_invocation(runner, original).cell, (1, 2, 0))
        self.assertEqual(runner.value, 42)
        self.assertFalse(packets)
        self.assertFalse(handler.prepared)
        self.assertFalse(handler.runners)


if __name__ == "__main__":
    unittest.main()
