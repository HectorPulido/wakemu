import unittest
from types import SimpleNamespace
from wakfu_server.combat_effect_dispatch import EffectInvocation
from wakfu_server.combat_final_modifier import final_modifier_source
from wakfu_server.combat_trigger_value_modifier import NativeRunnerAmount
from wakfu_server.combat_trigger_value_handler import NativeTriggerValueHandler
from wakfu_server.combat_stat_handler import StatExecutionContext, NativeStatHandler
from wakfu_server.combat_native_timing_context import native_time_payload


class TriggerValueHandlerTests(unittest.TestCase):
    def test_event_clone_uses_allocated_uid_without_retaining_another_listener(self):
        from wakfu_server.combat_effect_dispatch import EffectDispatcher

        fight, handler, effect, invocation = self.fixture(retained=True)
        effect.update(
            parameter_count=3,
            probability_base=100,
            probability_per_level=0,
            minimum_level=1,
            maximum_level=200,
            children=[],
            criteria="",
            target_masks=[[], [67, 69], [], [], [], [], []],
        )
        seen = []

        def apply(effect, values, selected):
            seen.append(selected.native_running_uid)
            return handler(effect, values, selected)

        dispatcher = EffectDispatcher(
            {"123": effect},
            {430: apply},
            resolve=lambda effect, selected: (selected,),
            condition_context=lambda selected: None,
            probability_accepts=lambda probability, selected: True,
            group_cells=lambda *args: (),
            actor_position=lambda actor: (0, 0, 0),
        )
        runner = NativeRunnerAmount(1, 1013, rng=lambda: 0.5, value=100)
        source = SimpleNamespace(uid=1, effect_action_id=1013, runner_modifier=runner)
        with final_modifier_source(source):
            for uid in (901, 902):
                self.assertTrue(
                    dispatcher.execute_activation(
                        invocation,
                        source=source,
                        condition_context=lambda *args: None,
                        executable=True,
                        allocate_uid=lambda uid=uid: uid,
                    )
                )
        self.assertEqual(seen, [901, 902])
        self.assertEqual(runner.value, 150)
        self.assertEqual(fight.owned_stat_effects, {})

    def fixture(self, *, retained=False):
        fight = SimpleNamespace(
            phase="active", actors={7: object(), 8: object()}, owned_stat_effects={}
        )
        context = StatExecutionContext(
            True, True, None, retained, native_time_payload(), None
        )
        handler = NativeTriggerValueHandler(
            fight, allocate_uid=lambda: 99, context=lambda *args: context
        )
        effect = {"effect_class": 430, "parameters": [1, 0, 25, 0, 0, 0]}
        invocation = EffectInvocation(123, 200, 7, 8, (0, 0, 0))
        return fight, handler, effect, invocation

    def test_original_source_mutation_has_no_actor_stat_write_or_pr_packet(self):
        fight, handler, effect, invocation = self.fixture()
        runner = NativeRunnerAmount(1, 1013, rng=lambda: 0.5, value=100)
        source = SimpleNamespace(uid=1, effect_action_id=1013, runner_modifier=runner)
        with final_modifier_source(source):
            self.assertTrue(handler(effect, {}, invocation))
        self.assertEqual(runner.value, 125)
        self.assertEqual(fight.owned_stat_effects, {})

    def test_own_retained_runner_keeps_identity_without_reversible_actor_delta(self):
        fight, handler, effect, invocation = self.fixture(retained=True)
        self.assertTrue(handler(effect, {}, invocation))
        row = fight.owned_stat_effects[99]
        self.assertEqual(
            (row["family"], row["stat_id"], row["actual"]), ("eZL", None, 25)
        )

    def test_missing_live_mutable_source_is_an_explicit_failure(self):
        fight, handler, effect, invocation = self.fixture()
        with final_modifier_source(
            SimpleNamespace(uid=1, effect_action_id=1013, runner_modifier=None)
        ):
            with self.assertRaises(ValueError):
                handler(effect, {}, invocation)
        self.assertEqual(fight.owned_stat_effects, {})

    def test_retained_removal_does_not_reverse_source_mutation(self):
        fight, handler, effect, invocation = self.fixture(retained=True)
        fight.id = 5
        fight.actors[8] = SimpleNamespace(id=8)
        runner = NativeRunnerAmount(1, 1013, rng=lambda: 0.5, value=100)
        source = SimpleNamespace(uid=1, effect_action_id=1013, runner_modifier=runner)
        with final_modifier_source(source):
            handler(effect, {}, invocation)
        remover = object.__new__(NativeStatHandler)
        remover.fight, remover.action_id, remover.packets = fight, 9, []
        remover.remove(99)
        self.assertEqual(runner.value, 125)
        self.assertEqual(fight.owned_stat_effects, {})
        self.assertEqual(remover.packets[0][0], 13560)
