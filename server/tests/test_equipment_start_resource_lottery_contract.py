"""Original whole-source AP lottery admission and ordered fallback semantics."""
import copy
import unittest

from test_equipment_start_heal_contract import original_graph
from wakfu_server.combat_effect_groups import decode_group_mode, execute_ordered_group
from wakfu_server.combat_equipment_start_resource_lottery_contract import (
    start_resource_lottery_contract,
)
from wakfu_server.combat_static_catalogs import characteristic_registry


class EquipmentStartResourceLotteryContractTests(unittest.TestCase):
    def test_original_complete_source_qualifies(self):
        self.assertIsNone(
            start_resource_lottery_contract(
                *original_graph(13574), characteristic_registry()
            )
        )

    def test_native_one_success_runs_fallback_only_after_first_child_fails(self):
        mode = decode_group_mode((1, 1))
        for first_succeeds, expected in ((True, [67471]), (False, [67471, 67470])):
            with self.subTest(first_succeeds=first_succeeds):
                calls = execute_ordered_group(
                    mode,
                    (67471, 67470),
                    caster_id=7,
                    target_id=7,
                    target_cell=(0, 0, 0),
                    execute_child=lambda row: first_succeeds
                    if row.child_id == 67471
                    else True,
                )
                self.assertEqual([row.child_id for row in calls], expected)

    def test_changed_probability_success_limit_context_timer_or_current_flags_reject(
        self,
    ):
        for change in (
            "probability",
            "limit",
            "count_successes",
            "criterion",
            "event",
            "order",
            "apply_current",
            "remove_current",
            "clock",
            "replace",
            "omitted",
        ):
            with self.subTest(change=change):
                source, compiled = copy.deepcopy(original_graph(13574))
                rows = compiled.effects
                root = rows[str(source["roots"][0])]
                state = compiled.source_states["states"][
                    str(int(root["parameters"][0]))
                ]
                carrier = rows[str(state["effect_ids"][0])]
                branch = rows[str(carrier["children"][0])]
                gain = rows[str(branch["children"][0])]
                if change == "probability":
                    branch["probability_base"] = 100
                elif change == "limit":
                    carrier["parameters"][0] = 2
                elif change == "count_successes":
                    carrier["parameters"][2] = 0
                elif change == "criterion":
                    carrier["criteria"] = ""
                elif change == "event":
                    carrier["target_masks"][5] = [1002]
                elif change == "order":
                    carrier["children"] = list(reversed(carrier["children"]))
                elif change == "apply_current":
                    gain["parameters"][2] = 0
                elif change == "remove_current":
                    gain["parameters"][4] = 1
                elif change == "clock":
                    gain["native_timing_definition"]["esr"] = False
                elif change == "replace":
                    state["replace"] = False
                else:
                    source["unplanned_passive_effect_ids"] = (123,)
                self.assertIsNotNone(
                    start_resource_lottery_contract(
                        source, compiled, characteristic_registry()
                    )
                )


if __name__ == "__main__":
    unittest.main()
