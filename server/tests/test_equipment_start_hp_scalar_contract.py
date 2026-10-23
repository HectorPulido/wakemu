"""Original complete start/HP scalar graphs and closed admission boundaries."""
import copy
import unittest

from test_equipment_start_heal_contract import original_graph
from wakfu_server.combat_equipment_start_hp_scalar_contract import (
    start_hp_scalar_state_contract,
)
from wakfu_server.combat_static_catalogs import characteristic_registry


class EquipmentStartHpScalarContractTests(unittest.TestCase):
    def test_all_three_original_complete_sources_qualify(self):
        for reference in (29446, 29447, 29448):
            with self.subTest(reference=reference):
                self.assertIsNone(
                    start_hp_scalar_state_contract(
                        *original_graph(reference), characteristic_registry()
                    )
                )

    def test_live_predicate_order_scalar_identity_timing_and_source_mutants_reject(
        self,
    ):
        for change in (
            "predicate",
            "event",
            "leaf_order",
            "amount",
            "stat",
            "clock",
            "area",
            "stack",
            "extra",
            "omitted",
        ):
            with self.subTest(change=change):
                source, compiled = copy.deepcopy(original_graph(29446))
                rows = compiled.effects
                root = rows[str(source["roots"][0])]
                state = compiled.source_states["states"][
                    str(int(root["parameters"][0]))
                ]
                carrier = rows[str(state["effect_ids"][0])]
                branch = rows[str(carrier["children"][0])]
                scalar = rows[str(branch["children"][1])]
                if change == "predicate":
                    branch["criteria"] = 'GetTotalHpInPercent("target") > 80'
                elif change == "event":
                    carrier["target_masks"][5] = [1002]
                elif change == "leaf_order":
                    branch["children"] = list(reversed(branch["children"]))
                elif change == "amount":
                    scalar["parameters"][1] = 1
                elif change == "stat":
                    scalar["parameters"][4] = 4
                elif change == "clock":
                    scalar["native_timing_definition"]["esr"] = False
                elif change == "area":
                    scalar["area_native"] = "point"
                    scalar["area_class"] = "anD"
                elif change == "stack":
                    state["additive"] = True
                elif change == "extra":
                    branch["children"] = [*branch["children"], branch["children"][0]]
                else:
                    source["unplanned_passive_effect_ids"] = (123,)
                self.assertIsNotNone(
                    start_hp_scalar_state_contract(
                        source, compiled, characteristic_registry()
                    )
                )


if __name__ == "__main__":
    unittest.main()
