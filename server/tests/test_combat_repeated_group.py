import unittest
from wakfu_server.combat_repeated_group import (
    NativePtResult,
    repeat_specification,
    execute_repeated_group,
)


class RepeatedGroupTests(unittest.TestCase):
    def test_cap_zero_and_negative_native_counts(self):
        effect = {"effect_class": 949}
        for count, expected in [(50, 12), (2, 2), (0, 0), (-2, 0)]:
            calls = []
            applied, iterations = execute_repeated_group(
                repeat_specification(effect, {"parameters": [count]}),
                [7],
                lambda child: calls.append(child) or NativePtResult(True, 1, False),
            )
            self.assertEqual(len(calls), expected)
            self.assertEqual(len(iterations), expected)
            self.assertFalse(applied)  # Native PT acceptance is separate.

    def test_null_pt_does_not_stop_but_nonnull_empty_does(self):
        spec = repeat_specification({"effect_class": 949}, {"parameters": [12, 1]})
        _, iterations = execute_repeated_group(
            spec, [7], lambda child: NativePtResult(False, 0, False)
        )
        self.assertEqual(len(iterations), 12)
        _, iterations = execute_repeated_group(
            spec, [7], lambda child: NativePtResult(True, 0, False)
        )
        self.assertEqual(len(iterations), 1)

    def test_finish_all_children_before_stopping_and_reevaluate(self):
        spec = repeat_specification({"effect_class": 949}, {"parameters": [4, 1]})
        calls = []

        def execute(child):
            calls.append(child)
            return NativePtResult(True, 1 if len(calls) < 3 else 0, False)

        _, iterations = execute_repeated_group(spec, [7, 8], execute)
        self.assertEqual(calls, [7, 8, 7, 8])
        self.assertEqual(iterations[-1]["empty"], 2)

    def test_bool_handler_result_cannot_masquerade_as_pt(self):
        spec = repeat_specification({"effect_class": 949}, {"parameters": [1, 1]})
        with self.assertRaises(ValueError):
            execute_repeated_group(spec, [7], lambda child: False)


class DispatcherPtTests(unittest.TestCase):
    def dispatcher(self, counter, *, criteria="", subscribed=False):
        from types import SimpleNamespace
        from test_combat_effect_dispatch import effect
        from wakfu_server.combat_effect_dispatch import EffectDispatcher
        from wakfu_server.combat_conditions import ConditionContext

        retention = SimpleNamespace(
            is_subscription=lambda definition, inv: subscribed and inv.reference == 91,
            begin_group=lambda *args: object() if subscribed else None,
            finish_group=lambda *args: None,
            probability_bypassed=lambda *args: False,
            child_level_context=lambda definition, values, inv, **kwargs: (
                inv.level,
                b"",
            ),
        )

        def handler(*args):
            counter["applied"] += 1
            return False

        return EffectDispatcher(
            {
                "90": effect(949, (12, 1), children=(91,)),
                "91": effect(400, criteria=criteria),
            },
            {400: handler},
            resolve=lambda definition, inv: (inv,),
            condition_context=lambda inv: ConditionContext(
                {}, caster_target_distance=counter["applied"]
            ),
            probability_accepts=lambda *args: True,
            group_cells=lambda *args: (),
            actor_position=lambda uid: (0, 0, 0),
            group_retention=retention,
            pt_preflight=lambda definition, inv: True,
        )

    def test_pt_count_independent_of_false_handler_result(self):
        from wakfu_server.combat_effect_dispatch import EffectInvocation

        counter = {"applied": 0}
        dispatcher = self.dispatcher(counter)
        self.assertFalse(dispatcher.execute(EffectInvocation(90, 1, 7, 7, (0, 0, 0))))
        self.assertEqual(counter["applied"], 12)

    def test_child_conditions_rebound_after_each_iteration(self):
        from wakfu_server.combat_effect_dispatch import EffectInvocation

        counter = {"applied": 0}
        dispatcher = self.dispatcher(
            counter, criteria="GetDistanceBetweenCasterAndTarget() < 2"
        )
        dispatcher.execute(EffectInvocation(90, 1, 7, 7, (0, 0, 0)))
        self.assertEqual(counter["applied"], 2)

    def test_subscription_registration_has_empty_execution_pt(self):
        from wakfu_server.combat_effect_dispatch import EffectInvocation

        counter = {"applied": 0}
        dispatcher = self.dispatcher(counter, subscribed=True)
        result = dispatcher.execute_pt(EffectInvocation(91, 1, 7, 7, (0, 0, 0)))
        self.assertTrue(result.applied)
        self.assertEqual(result.accepted_count, 0)
        self.assertEqual(counter["applied"], 0)

    def test_unknown_preflight_rejects_before_mutation(self):
        from wakfu_server.combat_effect_dispatch import EffectInvocation

        counter = {"applied": 0}
        dispatcher = self.dispatcher(counter)
        dispatcher.pt_preflight = lambda *args: None
        with self.assertRaises(ValueError):
            dispatcher.execute(EffectInvocation(90, 1, 7, 7, (0, 0, 0)))
        self.assertEqual(counter["applied"], 0)
