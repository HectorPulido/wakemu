import unittest
from unittest.mock import patch
from types import SimpleNamespace

from wakfu_server.combat_spell_resource_costs import (
    resolve,
    hupper_delta,
    extra_costs,
    pay_extra_resources,
)
from wakfu_server.combat_conditions import UnknownCondition


class SpellResourceCostTests(unittest.TestCase):
    def test_full_table_replaces_extra_resource_alongside_legacy_costs(self):
        records = {
            "9": dict(
                maximum_level=1,
                baseline=dict(resources={"2": [2, 2], "111": [-200, -200]}),
                conditional=[
                    dict(criteria="True", resources={"2": [2, 2], "111": [-100, -100]})
                ],
            )
        }
        with patch(
            "wakfu_server.combat_spell_resource_costs.evaluate_condition",
            return_value=True,
        ):
            self.assertEqual(resolve(9, 1, None, records=records), {2: 2, 111: -100})

    def test_unknown_extra_resource_difference_is_not_equivalent(self):
        records = {
            "9": dict(
                maximum_level=0,
                baseline=dict(resources={"2": [2]}),
                conditional=[
                    dict(criteria="unknown", resources={"2": [2], "111": [-100]})
                ],
            )
        }
        with patch(
            "wakfu_server.combat_spell_resource_costs.evaluate_condition",
            side_effect=UnknownCondition("unknown"),
        ):
            with self.assertRaises(UnknownCondition):
                resolve(9, 0, None, records=records)

    def test_signed_resource_uses_native_direction_and_rounding(self):
        self.assertEqual(hupper_delta(-201, {112: -25, 113: 50}), -150)
        self.assertEqual(hupper_delta(201, {112: -25, 113: 50}), 301)
        self.assertEqual(hupper_delta(201, {112: -25}), 151)
        self.assertEqual(
            extra_costs({111: -200, 123: 3}, SimpleNamespace(effect_stats={})),
            {111: -200, 123: -3},
        )

    def test_bounded_payment_and_insufficient_resource_leave_original_intact(self):
        actor = SimpleNamespace(effect_stats={111: 300}, effect_frozen=set())

        def snapshot(actor, stat):
            return actor.effect_stats[stat], 500, 500, 0, 0, 0, 0, 999

        def write(actor, stat, current, raw, maximum):
            actor.effect_stats[stat] = current

        with patch("wakfu_server.combat_maximum_resource._snapshot", snapshot), patch(
            "wakfu_server.combat_maximum_resource._write", write
        ):
            receipt = pay_extra_resources(actor, {111: -200})
            self.assertEqual(actor.effect_stats[111], 100)
            self.assertEqual(receipt[0]["actual_delta"], -200)
            with self.assertRaises(ValueError):
                pay_extra_resources(actor, {111: -200})
            self.assertEqual(actor.effect_stats[111], 100)
            pay_extra_resources(actor, {111: 800})
            self.assertEqual(actor.effect_stats[111], 500)

    def test_reuses_once_evaluated_selection_without_callback(self):
        records = {
            "9": dict(
                maximum_level=0,
                baseline=dict(resources={"2": [2]}),
                conditional=[dict(criteria="once", resources={"2": [3]})],
            )
        }
        selection = dict(
            reference=9,
            evaluation_level=0,
            evaluated_rules=[dict(index=0, criterion="once", result="matched")],
        )
        with patch(
            "wakfu_server.combat_spell_resource_costs.evaluate_condition",
            side_effect=AssertionError("queried twice"),
        ):
            self.assertEqual(
                resolve(9, 0, None, records=records, selection=selection), {2: 3}
            )

    def test_matching_extra_only_differences_remain_ambiguous(self):
        records = {
            "9": dict(
                maximum_level=0,
                baseline=dict(resources={"2": [2]}),
                conditional=[
                    dict(criteria=c, resources={"2": [2], "111": [v]})
                    for c, v in (("a", -100), ("b", -200))
                ],
            )
        }
        selection = dict(
            reference=9,
            evaluation_level=0,
            evaluated_rules=[
                dict(index=i, criterion=c, result="matched")
                for i, c in enumerate(("a", "b"))
            ],
        )
        with self.assertRaises(UnknownCondition):
            resolve(9, 0, None, records=records, selection=selection)
