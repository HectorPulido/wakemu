import unittest

from wakfu_server.equipment_resource_projection import (
    apply_operation,
    remove_operation,
    trace,
)


def _row(*, current=6, raw_minimum=0, raw_maximum=6, percentage=0):
    return {
        "current": current,
        "raw_minimum": raw_minimum,
        "raw_maximum": raw_maximum,
        "percentage": percentage,
        "hard_minimum": 0,
        "hard_maximum": 100,
    }


class EquipmentResourceProjectionTests(unittest.TestCase):
    def test_companion_equipment_dispatches_eWO_resource_reductions_by_native_family(
        self,
    ):
        from wakfu_server import equipment_stats
        from wakfu_server.companion_equipment import (
            SLOTS,
            pseudo_character,
            criterion_context,
        )
        from wakfu_server.equipment import RULES
        from wakfu_server.equipment_resource_bonuses import (
            reduction,
            from_native_values,
        )
        from wakfu_server.combat_actor_snapshot import native_npc_creation_values

        breed, level = 2828, 20
        values = native_npc_creation_values(breed, level)
        resource_baseline = from_native_values(values)
        native_baseline = {identity: row["current"] for identity, row in values.items()}
        owner = {"id": 77, "account_id": 88}
        context = criterion_context(owner, level, resource_baseline)
        expected_families = {56: 2, 57: 3, 192: 4}
        rows = []
        for reference, template in sorted(equipment_stats.CATALOG.items()):
            rule = RULES.get(reference)
            if rule is None or not set(rule["slots"]) & SLOTS:
                continue
            effects = [
                effect
                for effect in template["effects"]
                if effect.get("generic") in expected_families
                and reduction(effect) is not None
            ]
            if effects:
                rows.append((reference, rule, effects))
        self.assertTrue(rows)

        exercised = set()
        for reference, rule, effects in rows:
            slot = next(slot for slot in rule["slots"] if slot in SLOTS)
            item = {"uid": reference + 1, "reference": reference, "quantity": 1}
            character = pseudo_character(
                [dict(slot=slot, entry={"item": item})], owner, level
            )
            result = equipment_stats.bonuses(
                character,
                criterion_context=context,
                native_baseline=native_baseline,
                _selected_entries=[dict(uid=item["uid"], slot=slot)],
            )
            unsupported_ids = {row.get("effect_id") for row in result["unsupported"]}
            for effect in effects:
                with self.subTest(reference=reference, effect=effect["id"]):
                    self.assertNotIn(effect["id"], unsupported_ids)
                    self.assertNotIn(
                        effect["id"],
                        {row["effect_id"] for row in result["hp_operations"]},
                    )
                    stat, amount = reduction(effect)
                    self.assertIn((stat, amount, True), result["stat_operations"])
                    exercised.add(effect["generic"])
        self.assertEqual(exercised, set(expected_families))

    def test_native_eWO_ap_mp_catalog_census_and_inverse(self):
        from wakfu_server.equipment_resource_bonuses import reduction
        from wakfu_server.equipment_stats import CATALOG

        rows = [
            (reference, effect)
            for reference, item in CATALOG.items()
            for effect in item["effects"]
            if effect.get("runner") == "eWO" and effect.get("generic") in (56, 57)
        ]
        self.assertEqual(len({reference for reference, _ in rows}), 39)
        self.assertEqual(len(rows), 40)  # reference 15987 carries both AP and MP.

        for reference, effect in rows:
            with self.subTest(reference=reference, effect=effect.get("id")):
                stat, amount = reduction(effect)
                self.assertEqual(stat, {56: 2, 57: 3}[effect["generic"]])
                self.assertEqual(amount, effect["values"][0])
                baseline = _row(current=6, raw_maximum=6)
                changed, receipt = apply_operation(
                    baseline, amount, "eWO", subtract=True
                )
                self.assertEqual(changed["raw_maximum"], 6 - amount)
                self.assertEqual(changed["maximum"], 6 - amount)
                restored = remove_operation(changed, receipt)
                self.assertEqual(restored["raw_maximum"], 6)
                self.assertEqual(restored["current"], 6)

    def test_eWO_inverse_applies_to_live_sibling_state(self):
        original = _row()
        after_first, first = apply_operation(original, 2, "eWO", subtract=True)
        after_second, second = apply_operation(after_first, 2, "eWO", subtract=True)

        after_first_removal = remove_operation(after_second, first)
        self.assertEqual(after_first_removal["raw_maximum"], 4)
        self.assertEqual(after_first_removal["maximum"], 4)
        self.assertEqual(after_first_removal["current"], 4)

        restored = remove_operation(after_first_removal, second)
        self.assertEqual(restored["raw_maximum"], 6)
        self.assertEqual(restored["current"], 6)
        self.assertEqual(original["raw_maximum"], 6)

    def test_eWO_effective_int_maximum_skips_both_raw_bound_mutations(self):
        original = {
            **_row(current=5, raw_minimum=2, raw_maximum=(1 << 31) - 1),
            "hard_maximum": (1 << 31) - 1,
        }
        applied, _receipt = apply_operation(
            original,
            3,
            {"family": "eWO", "reduce_current": False},
            subtract=True,
        )
        self.assertEqual(applied["raw_minimum"], 2)
        self.assertEqual(applied["raw_maximum"], (1 << 31) - 1)
        self.assertEqual(applied["maximum"], (1 << 31) - 1)

    def test_eWN_AP_removal_uses_raw_actual_not_effective_delta(self):
        original = _row(current=15, raw_maximum=10, percentage=50)
        applied, receipt = apply_operation(
            original,
            2,
            {"family": "eWN", "apply_current": True, "remove_current": True},
            subtract=True,
        )
        self.assertEqual(receipt["actual"], -2)
        self.assertEqual(receipt["effective_delta"], -3)
        # PA.op first clamps 15 to 12, then eWN.nG applies the -3 effective
        # delta, producing 9 under this deliberately capped fixture.
        self.assertEqual(applied["current"], 9)

        removed = remove_operation(applied, receipt)
        self.assertEqual(removed["raw_maximum"], 10)
        self.assertEqual(removed["maximum"], 15)
        # Native eWN.bbR subtracts raw `actual` for AP/MP/WP; it does not
        # restore the effective -3 delta.
        self.assertEqual(removed["current"], 11)

    def test_trace_preserves_order_and_emits_removal_receipts(self):
        result = trace(
            [(2, 1, True), (3, 2, True)],
            {2: _row(), 3: _row()},
            {2: "eWO", 3: "eWO"},
        )
        self.assertEqual([step["stat"] for step in result["steps"]], [2, 3])
        self.assertEqual(result["maxima"], {2: 5, 3: 4})
        self.assertEqual(len(result["inverses"]), 2)

    def test_rejects_values_outside_native_java_int_range(self):
        with self.assertRaises(ValueError):
            apply_operation(_row(), 1 << 31, "eWO", subtract=True)
        with self.assertRaises(ValueError):
            apply_operation({**_row(), "raw_maximum": 1 << 31}, 1, "eWO", subtract=True)


if __name__ == "__main__":
    unittest.main()
