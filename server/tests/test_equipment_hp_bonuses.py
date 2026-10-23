import unittest

from wakfu_server.items.equipment_hp_bonuses import apply, descriptor, remove


class EquipmentHpBonusesTests(unittest.TestCase):
    # These are the original eWO + fff PA outputs captured in
    # .runtime/equipment-getcharac-20261020/ewo-hp-raw-boundary.log.
    # The current inputs are [0, 1, 14, 15, 16, 500, 1000] at max HP 1000.
    CASES = {
        10040: (
            47526,
            40,
            True,
            [0, 0, 0, 0, 0, 460, 960],
            [40, 40, 40, 40, 40, 500, 1000],
            [0, 0, 0, 0, 0, 460, 1000],
            [40, 40, 40, 40, 40, 500, 1000],
        ),
        10150: (
            135401,
            50,
            False,
            [0, 0, 0, 0, 0, 450, 950],
            [0, 0, 0, 0, 0, 450, 1000],
            [0, 0, 0, 0, 0, 450, 1000],
            [0, 0, 0, 0, 0, 450, 1000],
        ),
        20666: (
            183230,
            50,
            True,
            [0, 0, 0, 0, 0, 450, 950],
            [50, 50, 50, 50, 50, 500, 1000],
            [0, 0, 0, 0, 0, 450, 1000],
            [50, 50, 50, 50, 50, 500, 1000],
        ),
        23828: (
            217875,
            100,
            True,
            [0, 0, 0, 0, 0, 400, 900],
            [100, 100, 100, 100, 100, 500, 1000],
            [0, 0, 0, 0, 0, 400, 1000],
            [100, 100, 100, 100, 100, 500, 1000],
        ),
        24037: (
            237140,
            50,
            True,
            [0, 0, 0, 0, 0, 450, 950],
            [50, 50, 50, 50, 50, 500, 1000],
            [0, 0, 0, 0, 0, 450, 1000],
            [50, 50, 50, 50, 50, 500, 1000],
        ),
        5580: (
            217879,
            50,
            True,
            [0, 0, 0, 0, 0, 450, 950],
            [50, 50, 50, 50, 50, 500, 1000],
            [0, 0, 0, 0, 0, 450, 1000],
            [50, 50, 50, 50, 50, 500, 1000],
        ),
        6583: (
            55178,
            15,
            True,
            [0, 0, 0, 0, 1, 485, 985],
            [15, 15, 15, 15, 16, 500, 1000],
            [0, 0, 0, 0, 1, 485, 1000],
            [15, 15, 15, 15, 16, 500, 1000],
        ),
    }
    CURRENTS = [0, 1, 14, 15, 16, 500, 1000]

    @staticmethod
    def _effect(effect_id, amount, reference):
        values = [amount] if reference != 10150 else [50, 1, 0]
        return dict(
            generic=21,
            id=effect_id,
            runner="eWO",
            stat_id=-1,
            parameter_count=len(values),
            values=values,
            effect_criteria=False,
            has_triggers=False,
            target_mask=0,
            native_variant=0,
            native_active_effect=False,
            native_execution_mode=0,
        )

    @staticmethod
    def _root(effect_id, amount, reference):
        params = [float(amount), 0.0]
        values = [amount]
        if reference == 10150:
            params = [50.0, 0.0, 1.0, 0.0, 0.0, 0.0]
            values = [50, 1, 0]
        return dict(
            reference=effect_id,
            effect_class=21,
            variant=0,
            minimum_level=0,
            maximum_level=32767,
            parameters=params,
            parameter_count=len(values),
            criterion_raw="",
            native_values_at_fresh_item_level=values,
            children=[],
            child_definitions=[],
            metadata=dict(
                native_target_selector={"class": "fcE", "mask": 0},
                native_effect_flags=[],
                native_execution_mode=0,
                native_active_effect=False,
                native_definition_class="eVE",
                native_timing_definition={
                    "clock_on_caster": False,
                    "clock_on_target": True,
                },
                native_localization_enabled=False,
                application_flag="NONE",
                removal_flag="NONE",
                probability_base=100.0,
                probability_per_level=0.0,
                area_class="anA",
                area_native="empty",
            ),
        )

    @staticmethod
    def _state(current):
        return dict(
            raw_current=current,
            raw_minimum=0,
            raw_maximum=1000,
            hard_minimum=0,
            hard_maximum=1000,
            maximum_percentage=0,
        )

    def test_all_seven_native_hp_roots_match_original_pa_boundaries(self):
        for reference, (
            effect_id,
            amount,
            restore,
            after,
            removed,
            raw_after,
            raw_removed,
        ) in self.CASES.items():
            with self.subTest(reference=reference):
                operation = descriptor(self._effect(effect_id, amount, reference))
                if reference == 10150:
                    # Its second native operand selects a 1% branch. The PA
                    # arithmetic is qualified separately from RNG admission.
                    self.assertEqual(operation.pop("chance"), 1)
                    operation = dict(
                        family="eWO",
                        stat=1,
                        amount=amount,
                        reduce_current=True,
                        restore_current=restore,
                    )
                self.assertEqual(
                    operation,
                    dict(
                        family="eWO",
                        stat=1,
                        amount=amount,
                        reduce_current=True,
                        restore_current=restore,
                    ),
                )
                for current, expected_after, expected_removed in zip(
                    self.CURRENTS, after, removed
                ):
                    with self.subTest(reference=reference, current=current):
                        state, receipt = apply(self._state(current), operation)
                        self.assertEqual(state["minimum"], 0)
                        self.assertEqual(state["maximum"], 1000 - amount)
                        self.assertEqual(
                            max(
                                state["minimum"],
                                min(state["maximum"], state["raw_current"]),
                            ),
                            expected_after,
                        )
                        self.assertEqual(
                            state["raw_current"],
                            raw_after[self.CURRENTS.index(current)],
                        )
                        self.assertEqual(state["raw_minimum"], -amount)
                        self.assertEqual(state["raw_maximum"], 1000 - amount)
                        restored = remove(state, receipt)
                        self.assertEqual(restored["maximum"], 1000)
                        self.assertEqual(restored["minimum"], 0)
                        self.assertEqual(
                            max(
                                restored["minimum"],
                                min(restored["maximum"], restored["raw_current"]),
                            ),
                            expected_removed,
                        )
                        self.assertEqual(
                            restored["raw_current"],
                            raw_removed[self.CURRENTS.index(current)],
                        )

    def test_descriptor_rejects_non_native_or_unqualified_roots(self):
        reference = 6583
        effect = self._effect(55178, 15, reference)
        root = self._root(55178, 15, reference)
        for field, value in (
            ("generic", True),
            ("parameter_count", True),
            ("generic", 20),
            ("runner", "eWN"),
            ("effect_criteria", True),
            ("has_triggers", True),
            ("target_mask", False),
            ("target_mask", 1),
            ("native_variant", False),
            ("native_variant", 1),
            ("native_active_effect", True),
            ("stat_id", 2),
        ):
            invalid = dict(effect, **{field: value})
            with self.subTest(field=field):
                self.assertIsNone(descriptor(invalid))
        probabilistic = descriptor(dict(effect, values=[15, 1, 0], parameter_count=3))
        self.assertEqual(probabilistic["chance"], 1)
        with self.assertRaisesRegex(ValueError, "Unresolved native HP"):
            apply(self._state(500), probabilistic)

    def test_hp_raw_state_and_operation_values_are_signed_java_ints(self):
        operation = descriptor(self._effect(55178, 15, 6583))
        with self.assertRaises(ValueError):
            apply(dict(self._state(1001), raw_current=1 << 31), operation)
        with self.assertRaises(ValueError):
            apply(self._state(100), dict(operation, amount=1 << 31))

    def test_remove_applies_to_live_sibling_state_and_keeps_raw_hp_semantics(self):
        operation = descriptor(self._effect(55178, 15, 6583))
        state, receipt = apply(self._state(500), operation)
        # A sibling heal after the equipment operation remains present when the
        # equipment root is removed; removal runs on current PA state.
        state["raw_current"] += 25
        restored = remove(state, receipt)
        self.assertEqual(restored["raw_current"], 525)
        self.assertEqual(restored["maximum"], 1000)

    def test_two_native_roots_remove_in_either_order_against_live_pa_state(self):
        roots = (
            descriptor(self._effect(47526, 40, 10040)),
            descriptor(self._effect(183230, 50, 20666)),
        )
        # Native JVM witness: .runtime/equipment-getcharac-20261020/ewo-hp-multi-root.log
        cases = {
            0: (0, ((40, 950, -50), (50, 960, -40)), 90),
            500: (410, ((450, 950, -50), (460, 960, -40)), 500),
            1000: (1000, ((950, 950, -50), (960, 960, -40)), 1000),
        }
        for current, (after_both, after_first_removal, final) in cases.items():
            for first_index in (0, 1):
                with self.subTest(current=current, first_removed=first_index):
                    state = self._state(current)
                    state, first_receipt = apply(state, roots[0])
                    state, second_receipt = apply(state, roots[1])
                    self.assertEqual(state["raw_current"], after_both)
                    removal_order = (
                        ((first_receipt, 0), (second_receipt, 1))
                        if first_index == 0
                        else ((second_receipt, 1), (first_receipt, 0))
                    )
                    state = remove(state, removal_order[0][0])
                    (
                        expected_current,
                        expected_maximum,
                        expected_minimum,
                    ) = after_first_removal[first_index]
                    self.assertEqual(state["raw_current"], expected_current)
                    self.assertEqual(state["raw_maximum"], expected_maximum)
                    self.assertEqual(state["raw_minimum"], expected_minimum)
                    state = remove(state, removal_order[1][0])
                    self.assertEqual(state["raw_current"], final)
                    self.assertEqual(state["raw_maximum"], 1000)
                    self.assertEqual(state["raw_minimum"], 0)


if __name__ == "__main__":
    unittest.main()
