"""Ordered equipment characteristic replay uses native bounds and baselines."""
import unittest
from unittest.mock import patch

from wakfu_server.items.equipment_characteristics import native_rows, replay


class EquipmentCharacteristicReplayTests(unittest.TestCase):
    def _precheck_fixture(self, *, impossible=False, replacing_slot=False):
        from wakfu_server import builds, equipment, equipment_eligibility

        wisdom = next(
            identity
            for identity, row in native_rows().items()
            if row["minimum"] == -500 and row["maximum"] == 200
        )
        base = 190 if replacing_slot else 0
        baseline = {wisdom: base}
        character = {
            "id": 7,
            "active_build_index": 0,
            "builds": {0: {"equipment": ""}},
            "inventory_items": [
                {"uid": uid, "reference": 70000 + uid} for uid in (90, 101, 202, 303)
            ],
        }
        physical = [
            {"uid": 101, "slot": 0},
            {"uid": 202, "slot": 1},
            {"uid": 303, "slot": 2},
        ]
        old_entries = []
        old_result = {"stat_operations": (), "gear_operation_ranges": {}}
        old_inverse = ()
        if replacing_slot:
            old_entries = [{"uid": 90, "slot": 0}]
            # The existing +100 is clipped to +10 at baseline 190. Removing
            # the displaced item must apply that recorded inverse exactly once.
            old_result = {
                "stat_operations": ((wisdom, 100, False),),
                "gear_operation_ranges": {90: (0, 1)},
            }
            old_inverse = ((wisdom, 10, True),)
        operations = ((wisdom, 1, False), (wisdom, 2, False), (wisdom, 2, True))
        proposed = {
            "stat_operations": operations,
            "gear_operation_ranges": {101: (0, 1), 202: (1, 2), 303: (2, 3)},
        }

        def projection(_character, entries, **_kwargs):
            if any(row["uid"] != 90 for row in entries):
                return proposed, dict(baseline), dict(baseline), (None, None, None)
            return old_result, dict(baseline), dict(baseline), old_inverse

        tokens = {
            101: 'GetCharac("WISDOM") == 0',
            202: 'GetCharac("WISDOM") == 0',
            303: (
                'GetCharac("WISDOM") == 99'
                if impossible
                else 'GetCharac("WISDOM") == 2'
            ),
        }

        def evaluate(criterion, *, item, current_characteristics, **_kwargs):
            value = current_characteristics[wisdom]
            if replacing_slot and item["uid"] == 101:
                return value == 190
            if item["uid"] in (101, 202):
                return criterion == tokens[item["uid"]] and value == base
            return criterion == tokens[303] and value == base + (
                99 if impossible else 2
            )

        current_build = {
            "entries": old_entries,
            "current_characteristics": dict(baseline),
            "inverse_operations": old_inverse,
            "gear_operation_ranges": old_result["gear_operation_ranges"],
        }
        with patch.object(
            builds, "effective_sheet_level", return_value=100
        ), patch.object(
            equipment, "resolve_sheet", return_value=current_build
        ), patch.object(
            equipment_eligibility,
            "physical_sheet_entries",
            return_value=list(old_entries),
        ), patch.object(
            equipment_eligibility, "_projection", side_effect=projection
        ), patch.object(
            equipment_eligibility,
            "_condition",
            side_effect=lambda item: tokens[item["uid"]],
        ), patch.object(
            equipment_eligibility, "evaluate", side_effect=evaluate
        ):
            return equipment_eligibility.precheck_new(character, physical)

    def test_exact_addition_search_backtracks_from_dead_end_and_finds_legal_order(self):
        # Slot order starts with A. A is legal at baseline, but leaves no legal
        # next item. The valid sequence is B (+2), C (-2), A (+1). This is a
        # generic kernel fixture, not a claim about a particular native item.
        self._precheck_fixture()

    def test_exact_addition_search_rejects_when_no_legal_sequence_exists(self):
        from wakfu_server import equipment_eligibility

        with self.assertRaisesRegex(
            ValueError, "Native equipment EQUIP pre-application criteria"
        ):
            self._precheck_fixture(impossible=True)

    def test_slot_replacement_removes_clipped_old_contribution_once(self):
        # Baseline 190 plus an old +100 operation clips at WISDOM's native 200
        # cap, so the saved inverse is -10. A new same-slot unit is eligible
        # only after exactly that one inverse returns the actor to 190.
        self._precheck_fixture(replacing_slot=True)

    def test_many_nonqueried_additions_do_not_expand_an_impossible_search(self):
        from wakfu_server import builds, equipment, equipment_eligibility

        rows = native_rows()
        wisdom = next(
            identity
            for identity, row in rows.items()
            if row["minimum"] == -500 and row["maximum"] == 200
        )
        operation_stat = next(
            identity
            for identity in rows
            if identity != wisdom
            and not rows[identity]["expandable"]
            and not rows[identity]["frozen"]
        )
        baseline = {
            wisdom: rows[wisdom]["current"],
            operation_stat: rows[operation_stat]["current"],
        }
        items = [
            {"uid": 1000 + index, "reference": 71000 + index} for index in range(21)
        ]
        physical = [
            {"uid": item["uid"], "slot": index} for index, item in enumerate(items)
        ]
        operations = tuple((operation_stat, 1, False) for _ in items)
        ranges = {item["uid"]: (index, index + 1) for index, item in enumerate(items)}
        projected = {"stat_operations": operations, "gear_operation_ranges": ranges}
        empty = {"stat_operations": (), "gear_operation_ranges": {}}
        character = {
            "id": 7,
            "active_build_index": 0,
            "builds": {0: {"equipment": ""}},
            "inventory_items": items,
        }
        always = f'GetCharac("WISDOM") == {baseline[wisdom]}'
        impossible = f'GetCharac("WISDOM") == {baseline[wisdom] + 1}'
        criteria = {item["uid"]: always for item in items[:-1]}
        criteria[items[-1]["uid"]] = impossible
        calls = 0

        def evaluate(criterion, *, current_characteristics, **_kwargs):
            nonlocal calls
            calls += 1
            target = baseline[wisdom] if criterion == always else baseline[wisdom] + 1
            return current_characteristics[wisdom] == target

        def projection(_character, entries, **_kwargs):
            if entries:
                return (
                    projected,
                    dict(baseline),
                    dict(baseline),
                    (None,) * len(operations),
                )
            return empty, dict(baseline), dict(baseline), ()

        with patch.object(
            builds, "effective_sheet_level", return_value=100
        ), patch.object(
            equipment,
            "resolve_sheet",
            return_value={
                "entries": [],
                "current_characteristics": baseline,
                "inverse_operations": (),
                "gear_operation_ranges": {},
            },
        ), patch.object(
            equipment_eligibility, "physical_sheet_entries", return_value=[]
        ), patch.object(
            equipment_eligibility, "_projection", side_effect=projection
        ), patch.object(
            equipment_eligibility,
            "_condition",
            side_effect=lambda item: criteria[item["uid"]],
        ), patch.object(
            equipment_eligibility, "evaluate", side_effect=evaluate
        ):
            with self.assertRaisesRegex(
                ValueError, "Native equipment EQUIP pre-application criteria"
            ):
                equipment_eligibility.precheck_new(character, physical)

        # Twenty eligible additions do not change the queried PC. The kernel
        # can safely advance those entries without enumerating permutations;
        # the final impossible gate then rejects the batch.
        self.assertLess(calls, 100)

    def test_scalar_reduction_classifier_rejects_malformed_native_fields(self):
        from wakfu_server.equipment_stats import CATALOG, scalar_reduction

        source = next(
            effect
            for item in CATALOG.values()
            for effect in item["effects"]
            if scalar_reduction(effect)
        )
        self.assertTrue(scalar_reduction(source))
        malformed = (
            {"generic": "168"},
            {"generic": True},
            {"native_variant": False},
            {"target_mask": False},
            {"stat_limit": 0},
            {"values": [True]},
            {"stat_id": True},
        )
        for changes in malformed:
            with self.subTest(changes=changes):
                candidate = dict(source)
                candidate.update(changes)
                self.assertFalse(scalar_reduction(candidate))

    def test_native_companion_pet_levels_normalize_to_bounded_scalar_operations(self):
        from wakfu_server.equipment_stats import CATALOG, _flat, scalar_reduction
        from wakfu_server.combat_parameters import parameter_value

        for reference, stat_id, expected_by_level in (
            (32245, 9, {0: 0, 1: -1, 25: -25, 50: -50}),
            (32246, 11, {0: 0, 1: 0, 25: -2, 50: -5}),
        ):
            effect = next(
                effect
                for effect in CATALOG[reference]["effects"]
                if effect.get("runner") == "eWR" and effect.get("stat_id") == stat_id
            )
            self.assertTrue(scalar_reduction(effect))
            for level, expected in expected_by_level.items():
                with self.subTest(reference=reference, level=level):
                    value = parameter_value(effect["params"], 0, level)
                    level_effect = dict(effect, values=[value])
                    self.assertEqual(value, -expected)
                    self.assertEqual(_flat(level_effect), (stat_id, -value))
                    native = native_rows()[stat_id]
                    baseline = {stat_id: native["current"]}
                    expected_delta = (
                        max(native["minimum"], native["current"] - value)
                        - native["current"]
                    )
                    self.assertEqual(
                        replay([(stat_id, value, True)], [stat_id], baseline=baseline),
                        {stat_id: expected_delta},
                    )

    def test_all_published_scalar_reduction_rows_are_bound_to_native_fixed_stats(self):
        from wakfu_server.equipment_stats import (
            CATALOG,
            scalar_reduction,
            _scalar_parameters,
        )
        from wakfu_server.items.equipment_characteristics import native_rows

        rows = [
            effect
            for item in CATALOG.values()
            for effect in item["effects"]
            if effect.get("runner") == "eWR"
        ]
        qualified = [effect for effect in rows if scalar_reduction(effect)]
        rejected = [effect for effect in rows if not scalar_reduction(effect)]
        self.assertEqual(len(rows), 403)
        self.assertEqual(len(qualified), 403)
        self.assertEqual(len(rejected), 0)
        families = {}
        for effect in qualified:
            parsed = _scalar_parameters(effect)
            self.assertIsNotNone(parsed)
            families.setdefault(effect["generic"], set()).add(parsed["stat_id"])
        self.assertEqual(len(families), 25)
        self.assertEqual(
            len({_scalar_parameters(effect)["stat_id"] for effect in qualified}), 24
        )
        dynamic_reductions = [effect for effect in qualified if effect["generic"] == 40]
        self.assertEqual(
            {
                (effect["id"], effect["stat_id"], tuple(effect["values"]))
                for effect in dynamic_reductions
            },
            {(311431, -1, (40, 0, 121)), (311432, -1, (40, 0, 121))},
        )
        characteristics = native_rows()
        for effect in qualified:
            parsed = _scalar_parameters(effect)
            stat_id = parsed["stat_id"]
            amount = parsed["requested"]
            with self.subTest(effect_id=effect["id"], stat=effect["stat_id"]):
                row = characteristics[stat_id]
                self.assertFalse(row["expandable"])
                self.assertFalse(row["frozen"])
                expected = max(row["minimum"], row["current"] - amount) - row["current"]
                self.assertEqual(
                    replay([(stat_id, amount, True)], [stat_id]),
                    {stat_id: expected},
                )

    def test_mixed_subtract_then_add_uses_ordered_headroom_not_a_blind_sum(self):
        # Use the real native characteristic bounds/current value, but a
        # selected actor baseline near the upper edge to make ordering visible.
        characteristic = next(
            identity
            for identity, row in native_rows().items()
            if not row["expandable"]
            and not row["frozen"]
            and row["minimum"] == 0
            and row["maximum"] == 100
        )
        baseline = {characteristic: 90}
        ordered = replay(
            [(characteristic, 20, False), (characteristic, 20, True)],
            [characteristic],
            baseline=baseline,
        )
        reversed_order = replay(
            [(characteristic, 20, True), (characteristic, 20, False)],
            [characteristic],
            baseline=baseline,
        )
        self.assertEqual(ordered, {characteristic: -10})  # 90→100→80
        self.assertEqual(reversed_order, {characteristic: 0})  # 90→70→90

    def test_fifo_inverse_preserves_a_previously_clipped_later_contribution(self):
        # This exercises only the generic reconciliation kernel. Projection
        # operations and predicates are fixtures; characteristic bounds and
        # directed inverse arithmetic come from the real native catalog.
        from wakfu_server import equipment_eligibility
        from wakfu_server.items.equipment_characteristics import trace

        rows = native_rows()
        wisdom = next(
            identity
            for identity, row in rows.items()
            if row["minimum"] == -500 and row["maximum"] == 200
        )
        baseline = {
            identity: row["current"]
            for identity, row in rows.items()
            if not row["expandable"] and not row["frozen"]
        }
        baseline[wisdom] = 190
        operations = [(wisdom, 100, False), (wisdom, 100, False)]
        initial, current, inverse = trace(operations, baseline=baseline)
        self.assertEqual(current[wisdom], 200)  # first +100 applies only +10
        self.assertEqual(inverse[0], (wisdom, 10, True))
        self.assertEqual(inverse[1], (wisdom, 0, True))
        projection = dict(
            stats={wisdom: 10},
            stat_operations=tuple(operations),
            gear_operation_ranges={101: (0, 1), 202: (1, 2)},
        )
        character = {
            "inventory_items": [
                {"uid": 101, "reference": 70001},
                {"uid": 202, "reference": 70002},
            ]
        }
        physical = [{"uid": 101, "slot": 0}, {"uid": 202, "slot": 15}]

        def condition_result(criterion, **kwargs):
            if criterion == "first":
                return kwargs["current_characteristics"][wisdom] < 200
            return True

        with patch.object(
            equipment_eligibility,
            "_projection",
            return_value=(projection, initial, current, inverse),
        ), patch.object(
            equipment_eligibility,
            "_condition",
            side_effect=lambda item: "first" if item["uid"] == 101 else "later",
        ), patch.object(
            equipment_eligibility, "evaluate", side_effect=condition_result
        ):
            result = equipment_eligibility.reconcile(character, physical)

        self.assertEqual(result["entries"], [{"uid": 202, "slot": 15}])
        self.assertEqual(result["removed_uids"], frozenset({101}))
        self.assertEqual(result["current_characteristics"][wisdom], 190)
        # Replaying the later item alone would grant +10. Reconciliation
        # retains its zero actual contribution from the original capped pass.
        self.assertEqual(
            replay(operations[1:], [wisdom], baseline=baseline), {wisdom: 10}
        )
        self.assertEqual(result["scalar_overrides"][wisdom], 0)

    def test_removal_rebuilds_from_original_baseline_and_keeps_native_defaults(self):
        characteristic = next(
            identity
            for identity, row in native_rows().items()
            if not row["expandable"]
            and not row["frozen"]
            and row["minimum"] == 0
            and row["maximum"] == 100
        )
        default = native_rows()[characteristic]["current"]
        baseline = {characteristic: 90}
        with_both = replay(
            [(characteristic, 30, True), (characteristic, 70, False)],
            [characteristic],
            baseline=baseline,
        )
        after_removing_addition = replay(
            [(characteristic, 30, True)], [characteristic], baseline=baseline
        )
        from_default = replay([(characteristic, 25, False)], [characteristic])
        self.assertEqual(with_both, {characteristic: 10})  # 90→60→100
        self.assertEqual(after_removing_addition, {characteristic: -30})
        self.assertEqual(from_default[characteristic], min(100, default + 25) - default)

    def test_native_int32_clipping_and_expandable_resource_ownership(self):
        rows = native_rows()
        signed = next(
            identity
            for identity, row in rows.items()
            if not row["expandable"]
            and not row["frozen"]
            and row["minimum"] == -(1 << 31)
            and row["maximum"] == (1 << 31) - 1
        )
        baseline = {signed: 0}
        wrapped = replay([(signed, -(1 << 31), True)], [signed], baseline=baseline)
        self.assertEqual(wrapped, {signed: -(1 << 31)})
        self.assertEqual(rows[signed]["minimum"], -(1 << 31))

        expandable = next(
            identity for identity, row in rows.items() if row["expandable"]
        )
        with self.assertRaisesRegex(
            ValueError, "Unsupported ordered equipment characteristic"
        ):
            replay([], [expandable])

    def test_effective_delta_outside_native_range_is_rejected(self):
        characteristic = next(
            identity
            for identity, row in native_rows().items()
            if not row["expandable"]
            and not row["frozen"]
            and row["minimum"] == 0
            and row["maximum"] == 100
        )
        with self.assertRaisesRegex(
            ValueError, "Invalid native equipment characteristic baseline"
        ):
            replay([], [characteristic], baseline={characteristic: 101})


if __name__ == "__main__":
    unittest.main()
