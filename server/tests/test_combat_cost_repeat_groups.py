import unittest
from wakfu_server.combat_effect_dispatch import EffectInvocation
from wakfu_server.combat_cost_level_group import (
    cost_group_override,
    weighted_cost_level,
)
from wakfu_server.combat_repeat_group import execute_repeated_group, RepeatChildOutcome


class CostRepeatTests(unittest.TestCase):
    def definition(self, family):
        return dict(
            effect_class=family,
            parameters=[0.0, 0.0] * 6 + [1.0, 0.0, 0.5, 0.0, 2.0, 0.0],
        )

    def test_action_cost_bytes_and_absence_are_not_spell_costs(self):
        e = self.definition(912)
        self.assertEqual(
            cost_group_override(e, 20, source_present=False, cost_source=None), 20
        )
        self.assertEqual(
            cost_group_override(
                e, 20, source_present=True, cost_source={"runner_class": "other"}
            ),
            20,
        )
        s = {"runner_class": "eWf", "action_costs": {"ap": 3, "mp": 1, "wp": 2}}
        self.assertEqual(
            cost_group_override(e, 20, source_present=True, cost_source=s), 8
        )
        self.assertEqual(
            weighted_cost_level((0.5, 0.0, 0.0), dict(ap=-3, mp=0, wp=0)), -1
        )
        with self.assertRaises(ValueError):
            cost_group_override(e, 20, source_present=True, cost_source=None)

    def test_spell_costs_require_live_context_and_nospell_zero(self):
        e = self.definition(910)
        self.assertEqual(
            cost_group_override(e, 20, source_present=False, cost_source=None), 0
        )
        s = {"runner_class": "other", "spell_context": {"present": False}}
        self.assertEqual(
            cost_group_override(e, 20, source_present=True, cost_source=s), 0
        )
        s["spell_context"] = {
            "present": True,
            "container_type": 11,
            "resolved_costs": {"ap": 2, "mp": 2, "wp": 1},
        }
        self.assertEqual(
            cost_group_override(e, 20, source_present=True, cost_source=s), 5
        )
        with self.assertRaises(ValueError):
            cost_group_override(
                e, 20, source_present=True, cost_source={"runner_class": "other"}
            )

    def test_repeat_null_pt_does_not_stop_but_created_zero_does(self):
        e = dict(effect_class=949, parameters=[20.0, 0.0, 1.0, 0.0], children=[1, 2])
        calls = []

        def callback(ref, inv, iteration):
            self.assertIsNone(inv.target_id)
            calls.append((ref, iteration))
            return (
                RepeatChildOutcome(True, 0)
                if iteration == 1 and ref == 2
                else RepeatChildOutcome(False, None)
            )

        r = execute_repeated_group(
            e, EffectInvocation(379582, 1, 7, 7, (0, 0, 0)), execute_child=callback
        )
        self.assertEqual(len(r), 2)
        self.assertEqual(r[0]["failed"], 0)
        self.assertEqual(r[1]["failed"], 1)
        e["parameters"] = [20.0, 0.0]
        self.assertEqual(
            len(
                execute_repeated_group(
                    e,
                    EffectInvocation(379582, 1, 7, 7, (0, 0, 0)),
                    execute_child=callback,
                )
            ),
            12,
        )

    def test_repeat_rejects_ambiguous_bool_and_negative_count_executes_none(self):
        e = dict(effect_class=949, parameters=[1.0, 0.0], children=[1])
        with self.assertRaises(ValueError):
            execute_repeated_group(
                e,
                EffectInvocation(379582, 1, 7, 7, (0, 0, 0)),
                execute_child=lambda *a: False,
            )
        e["parameters"] = [-1.0, 0.0]
        self.assertEqual(
            execute_repeated_group(
                e,
                EffectInvocation(379582, 1, 7, 7, (0, 0, 0)),
                execute_child=lambda *a: False,
            ),
            [],
        )
