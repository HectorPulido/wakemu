import unittest
import json
import struct
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import patch

from wakfu_server.combat_native_spell_casting import definition
from wakfu_server.combat_conditions import (
    ConditionActor,
    ConditionContext,
    UnknownCondition,
    evaluate_condition,
)


class CastingSelectionProvenanceTests(unittest.TestCase):
    def select(self, results, costs):
        record = dict(
            costs=[[4, 0, 0]],
            levels=[[1, 5, []]],
            categories=[],
            line_of_sight=True,
            linear=False,
            free_cell=False,
            range_modifiable=False,
            path_option=False,
            diagonal=False,
            linear_path=False,
            allow_self=False,
            forbid_QI_P=False,
            cast_criterion_native_present=False,
        )
        flags = {
            key: record[key]
            for key in (
                "line_of_sight",
                "linear",
                "free_cell",
                "range_modifiable",
                "path_option",
                "diagonal",
                "linear_path",
                "allow_self",
            )
        }
        record["conditional"] = [
            dict(flags, criteria=str(index), levels=[[cost, 0, 0]], ranges=[[1, 5]])
            for index, cost in enumerate(costs)
        ]
        with patch(
            "wakfu_server.combat_native_spell_casting.catalog",
            return_value={"1": record},
        ), patch(
            "wakfu_server.combat_native_spell_casting.evaluate_condition",
            side_effect=results,
        ):
            return definition(1, 1, None, {})

    def test_baseline_and_equivalent_matches_keep_distinct_source_identity(self):
        baseline = self.select([False], [2])
        self.assertEqual(
            baseline["native_casting_selection"]["selected_origin"], "baseline"
        )
        selected = self.select([True, True], [2, 2])
        identity = selected["native_casting_selection"]
        self.assertEqual([row["index"] for row in identity["matched_rules"]], [0, 1])
        self.assertFalse(identity["unique_matching_rule"])
        self.assertEqual(selected["costs"]["ap"], 2)
        self.assertEqual(identity["selected_values"][0], 2)
        self.assertEqual(identity["baseline_values"][0], 4)

    def test_unresolved_equivalent_branch_is_recorded_without_false_unique_claim(self):
        selected = self.select([UnknownCondition("unknown"), True], [4, 4])
        identity = selected["native_casting_selection"]
        self.assertEqual(identity["unknown_equivalent_rule_indices"], [0])
        self.assertFalse(identity["unique_matching_rule"])

    def test_rejection_diagnostics_are_json_safe_and_do_not_recheck_conditions(self):
        from wakfu_server.combat_cast import prepare_spell_cast
        from wakfu_server.combat_conditional_costs import ConditionalCostContext
        from wakfu_server.spells import encode_deck

        actor = SimpleNamespace(
            id=7,
            owner_id=3,
            controlled=True,
            hp=60,
            ap=6,
            mp=3,
            team=0,
            effective_level=1,
            position=(0, 0, 0),
            turn_count=0,
            spell_ap_cost_modifiers={},
            spell_range_modifiers={},
        )
        fight = SimpleNamespace(
            id=77,
            phase="active",
            current=actor,
            actors={7: actor},
            walkable={(0, 0, 0)},
            native_table_turn=0,
        )
        caster = ConditionActor(
            state_ids=frozenset(),
            deck_spell_ids=frozenset({6260}),
            excluded_deck_spell_ids=frozenset(),
            is_player=True,
            is_carried=False,
            fight_properties=frozenset(),
            characteristics={"RANGE": 0},
        )
        conditions = ConditionContext({"caster": caster})
        query_diagnostic = {"trace": [{"stage": "eligibility", "value": "twV"}]}
        conditions = replace(
            conditions,
            native_casting_query=lambda *args: dict(
                result="twV",
                aligned=True,
                target_id=None,
                diagnostic=query_diagnostic,
            ),
        )
        body = struct.pack(">qqiih", 7, (7 << 32) | 6260, 0, 0, 0)
        callbacks = []
        with patch(
            "wakfu_server.combat_native_spell_casting.evaluate_condition",
            wraps=evaluate_condition,
        ) as evaluate:
            with self.assertRaisesRegex(ValueError, "eligibility rejected") as caught:
                prepare_spell_cast(
                    body,
                    dict(id=7, breed=15, level=1),
                    fight,
                    3,
                    encode_deck([6260]),
                    wp=6,
                    line_of_sight=lambda *args: True,
                    conditional_context=lambda *args: ConditionalCostContext(
                        conditions, {}
                    ),
                    diagnostic=callbacks.append,
                )
        details = caught.exception.cast_diagnostics
        self.assertEqual(callbacks, [details])
        self.assertEqual(caught.exception.native_casting_result, "twV")
        self.assertEqual(caught.exception.native_casting_diagnostic, query_diagnostic)
        self.assertEqual(evaluate.call_count, len(details["conditional_rules"]))
        serialized = json.loads(json.dumps(details))
        self.assertEqual(serialized["fight_id"], fight.id)
        self.assertEqual(
            serialized["selection"]["selected_values"],
            list(details["selection"]["selected_values"]),
        )

    def test_changed_unknown_or_ambiguous_tables_still_reject(self):
        for results, costs in (
            ([UnknownCondition("unknown")], [2]),
            ([True, True], [2, 3]),
        ):
            with self.assertRaises(UnknownCondition):
                self.select(results, costs)
