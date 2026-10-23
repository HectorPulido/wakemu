"""Resource equipment conditions preserve ordered PA receipts and raw bounds."""
from copy import deepcopy
from unittest import TestCase
from unittest.mock import patch

from wakfu_server import equipment_conditions as conditions
from wakfu_server import equipment_eligibility as eligibility
from wakfu_server.equipment_resource_projection import apply_operation


class EquipmentResourceEligibilityTests(TestCase):
    def baseline(self):
        return dict(
            current=6,
            raw_minimum=0,
            raw_maximum=6,
            minimum=0,
            maximum=6,
            percentage=0,
            hard_minimum=0,
            hard_maximum=2147483647,
        )

    def aliases(self):
        return {"AP": dict(id=2), "MP": dict(id=3), "WP": dict(id=4)}

    def result(self, operations, ranges, kinds):
        initial = {2: self.baseline()}
        states = deepcopy(initial)
        inverse = []
        for index, (identity, amount, subtract) in enumerate(operations):
            states[identity], receipt = apply_operation(
                states[identity], amount, kinds[index], subtract=subtract
            )
            inverse.append(receipt)
        result = dict(
            stat_operations=operations,
            gear_operation_ranges=ranges,
            stats={2: states[2]["maximum"] - 6},
            resource_kinds=kinds,
            resource_states=states,
            maximum_characteristics={2: states[2]["maximum"]},
        )
        return result, {2: 6}, {2: states[2]["current"]}, inverse

    def test_current_and_maximum_getters_are_distinct_and_read_only(self):
        current, maximum = {2: 0}, {2: 11}
        kwargs = dict(
            item=dict(uid=1, reference=1),
            selected=[],
            owned={},
            current_characteristics=current,
            maximum_characteristics=maximum,
        )
        with patch(
            "wakfu_server.combat_characteristic_conditions.native_aliases", self.aliases
        ):
            self.assertTrue(
                conditions.evaluate(
                    'GetCharac("AP") == 0 and GetCharacMax("AP") == 11', **kwargs
                )
            )
            self.assertTrue(
                conditions.evaluate(
                    'GetCharacteristicMax("AP", "target") == 11', **kwargs
                )
            )
            with self.assertRaises(ValueError):
                conditions.evaluate(
                    'GetCharacMax("AP", "triggeringcaster") == 11', **kwargs
                )
            with self.assertRaises(ValueError):
                conditions.evaluate('GetCharacMax("MP") == 0', **kwargs)
        self.assertEqual(current, {2: 0})
        self.assertEqual(maximum, {2: 11})

    def test_fifo_removal_uses_current_sibling_raw_state_and_preserves_resource_snapshot(
        self,
    ):
        character = dict(
            id=1,
            level=1,
            inventory_items=[dict(uid=10, reference=10), dict(uid=20, reference=20)],
        )
        physical = [dict(uid=10, slot=0), dict(uid=20, slot=3)]
        projected = self.result(
            [(2, 20, True), (2, 5, False)],
            {10: (0, 1), 20: (1, 2)},
            {0: dict(family="eWO"), 1: dict(family="eWN")},
        )
        with patch.object(
            eligibility, "_projection", return_value=projected
        ), patch.object(
            eligibility,
            "_condition",
            side_effect=lambda item: "False"
            if item["uid"] == 10
            else 'GetCharacMax("AP") >= 10',
        ), patch.object(
            eligibility, "native_rows", return_value={2: dict(maximum=2147483647)}
        ), patch(
            "wakfu_server.equipment_context.for_character",
            side_effect=lambda actor, context: context,
        ), patch(
            "wakfu_server.combat_characteristic_conditions.native_aliases", self.aliases
        ):
            result = eligibility.reconcile(character, physical)
        self.assertEqual(result["removed_uids"], frozenset({10}))
        self.assertEqual(result["maximum_characteristics"][2], 11)
        self.assertEqual(result["resource_states"][2]["raw_maximum"], 11)
        self.assertEqual(result["current_characteristics"][2], 11)
        self.assertNotIn(2, result["scalar_overrides"])

    def test_precheck_search_applies_resource_metadata_before_a_later_maximum_predicate(
        self,
    ):
        character = dict(
            id=1,
            level=1,
            active_build_index=0,
            builds={0: dict(equipment="")},
            inventory_items=[dict(uid=10, reference=10), dict(uid=20, reference=20)],
        )
        physical = [dict(uid=10, slot=0), dict(uid=20, slot=3)]
        empty = self.result([], {}, {})
        proposed = self.result(
            [(2, 5, False)], {10: (0, 0), 20: (0, 1)}, {0: dict(family="eWN")}
        )
        with patch.object(
            eligibility, "_projection", side_effect=[empty, proposed]
        ), patch.object(
            eligibility, "physical_sheet_entries", return_value=[]
        ), patch.object(
            eligibility,
            "_condition",
            side_effect=lambda item: 'GetCharacMax("AP") >= 11'
            if item["uid"] == 10
            else "True",
        ), patch.object(
            eligibility, "native_rows", return_value={2: dict(maximum=2147483647)}
        ), patch(
            "wakfu_server.equipment.resolve_sheet", return_value=dict(entries=[])
        ), patch(
            "wakfu_server.equipment_context.for_character",
            return_value=dict(actor_kind="player", level=1),
        ), patch(
            "wakfu_server.builds.effective_sheet_level", return_value=1
        ), patch(
            "wakfu_server.combat_characteristic_conditions.native_aliases", self.aliases
        ):
            eligibility.precheck_new(character, physical)

    def test_replacing_an_already_ineligible_unit_does_not_remove_its_resource_effect_twice(
        self,
    ):
        character = dict(
            id=1,
            level=1,
            active_build_index=0,
            builds={0: dict(equipment="")},
            inventory_items=[
                dict(uid=10, reference=10),
                dict(uid=20, reference=20),
                dict(uid=30, reference=30),
            ],
        )
        empty = self.result([], {}, {})
        for values in empty[1:3]:
            values[10] = 0
        proposed = deepcopy(empty)
        proposed[0].update(
            stat_operations=[(10, 1, False)],
            gear_operation_ranges={10: (0, 1), 20: (1, 1)},
        )
        _, old_receipt = apply_operation(
            self.baseline(), 20, dict(family="eWO"), subtract=True
        )
        old_receipt["stat"] = 2
        resolution = dict(
            entries=[],
            removed_uids=frozenset({30}),
            inverse_operations=[old_receipt],
            gear_operation_ranges={30: (0, 1)},
            resource_states={2: self.baseline()},
        )
        rows = {2: dict(maximum=2147483647), 10: dict(minimum=0, maximum=100)}
        aliases = dict(self.aliases(), TEST=dict(id=10))
        with patch.object(
            eligibility, "_projection", side_effect=[empty, proposed]
        ), patch.object(
            eligibility, "physical_sheet_entries", return_value=[dict(uid=30, slot=0)]
        ), patch.object(
            eligibility,
            "_condition",
            side_effect=lambda item: "True"
            if item["uid"] == 10
            else 'GetCharac("TEST") >= 1 and GetCharacMax("AP") <= 6',
        ), patch.object(
            eligibility, "native_rows", return_value=rows
        ), patch(
            "wakfu_server.equipment.resolve_sheet", return_value=resolution
        ), patch(
            "wakfu_server.equipment_context.for_character",
            return_value=dict(actor_kind="player", level=1),
        ), patch(
            "wakfu_server.builds.effective_sheet_level", return_value=1
        ), patch(
            "wakfu_server.combat_characteristic_conditions.native_aliases",
            return_value=aliases,
        ):
            eligibility.precheck_new(
                character,
                [dict(uid=10, slot=0), dict(uid=20, slot=3)],
                current_characteristics={10: 0},
            )
