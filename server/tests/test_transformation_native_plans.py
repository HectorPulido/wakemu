"""Exact native type738 direct and ordered-success consumption boundaries."""
import json
from pathlib import Path
import unittest

from wakfu_server.combat_effect_groups import decode_group_mode, execute_ordered_group
from wakfu_server.consumable_characteristics import bonuses
from wakfu_server.consumable_criteria import evaluate


class TransformationNativePlansTests(unittest.TestCase):
    def rows(self):
        path = Path(__file__).parents[1] / "protocol/native-consumable-actions.json"
        return [
            row
            for row in json.loads(path.read_text())["items"]
            if row["native_type"] == 738
        ]

    def test_all_original_transformations_have_timed_state_and_native_use_guard(self):
        rows = self.rows()
        self.assertEqual(len(rows), 36)
        for row in rows:
            with self.subTest(item=row["item_ref"]):
                plan = row["plan"]
                self.assertEqual(plan["consumable_scope"], "native-transformation")
                states = [
                    dict(state, remaining_ms=state["duration_ms"])
                    for state in plan["states"]
                ]
                self.assertTrue(states)
                self.assertFalse(bonuses(dict(consumable_states=states))["unsupported"])
                self.assertTrue(
                    evaluate(plan["criterion"], dict(map_id=1134, consumable_states=[]))
                )
                if plan["criterion"]:
                    self.assertFalse(
                        evaluate(
                            plan["criterion"],
                            dict(
                                map_id=1134,
                                consumable_states=[dict(state_id=531, level=1)],
                            ),
                        )
                    )
                self.assertTrue(
                    any(
                        state["metadata"].get("native_visual_effect_ids")
                        for state in states
                    )
                )

    def test_original_ordered_groups_choose_the_only_eligible_child_without_random_selection(
        self,
    ):
        grouped = [
            row for row in self.rows() if "native_item_group_policy" in row["plan"]
        ]
        self.assertEqual(len(grouped), 4)
        for row in grouped:
            with self.subTest(item=row["item_ref"]):
                plan = row["plan"]
                policy = plan["native_item_group_policy"]
                nodes = plan["native_item_effects"]
                parent = nodes[str(policy["root_id"])]
                self.assertEqual(parent["generic"], 330)
                mode = decode_group_mode(parent["values"])
                self.assertEqual(
                    (mode.limit, mode.count_successes, mode.relative_probability),
                    (1, True, False),
                )
                successful = []

                def execute(invocation):
                    node = nodes[str(invocation.child_id)]
                    if not evaluate(
                        node["criteria"], dict(map_id=1134, consumable_states=[])
                    ):
                        return False
                    successful.append(node)
                    return True

                calls = execute_ordered_group(
                    mode,
                    parent["children"],
                    caster_id=40,
                    target_id=40,
                    target_cell=(0, 0, 0),
                    execute_child=execute,
                )
                self.assertEqual([call.child_id for call in calls], parent["children"])
                self.assertEqual(
                    [node["id"] for node in successful], [policy["selected_child"]]
                )
                state = plan["states"][0]
                self.assertEqual(
                    successful[0]["values"][:2], [state["state_id"], state["level"]]
                )
