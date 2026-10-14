"""eLt FIRST-per-PV then maximum, with real tracked Qf order authority."""
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from wakfu_server.combat_state_max_level_range import (
    StateLevelPV,
    maximum_state_level,
    ordered_registered_state_carriers,
    state_level_population,
)
from wakfu_server.combat_conditions import (
    ConditionContext,
    ConditionActor,
    UnknownCondition,
    evaluate_condition,
)


class StateMaxLevelRangeTests(unittest.TestCase):
    def row(
        self,
        level,
        *,
        position=(0, 0, 0),
        radius=0,
        properties=frozenset(),
        carriers=None
    ):
        return StateLevelPV(
            position,
            radius,
            properties,
            ((6402, level, 7),) if carriers is None else carriers,
        )

    def query(self, rows, **changes):
        values = dict(center=(0, 0, 0), minimum=0, maximum=30, reference=6402)
        values.update(changes)
        return maximum_state_level(rows, **values)

    def test_native_missing_center_and_empty_population_are_distinct(self):
        self.assertEqual(self.query([], center=None), 0)
        self.assertEqual(self.query([]), -1)

    def test_first_per_pv_then_maximum_is_neither_sum_nor_within_pv_maximum(self):
        rows = [self.row(3, carriers=((6402, 3, 7), (6402, 19, 8))), self.row(5)]
        self.assertEqual(self.query(rows), 5)
        self.assertEqual(self.query(rows[:1], owner_id=8), 3)
        self.assertEqual(self.query(rows[:1], owner_id=99), -1)
        self.assertEqual(
            self.query(rows[:1], owner_id=8, native_caster_present=False), -1
        )

    def test_actual_radius_property_and_negative_maximum_contract(self):
        rows = [
            self.row(5, position=(3, 3, 19), radius=1),
            self.row(9, position=(3, 3, -19)),
            self.row(90, properties=frozenset({42})),
        ]
        self.assertEqual(self.query(rows, maximum=4), 5)
        self.assertEqual(self.query(rows, minimum=999, maximum=-1), 9)
        self.assertEqual(self.query(rows, minimum=1, maximum=1), -1)

    def test_registered_uid_order_controls_first_even_when_ledger_order_differs(self):
        manager = SimpleNamespace(
            id=7,
            state_ledger=SimpleNamespace(
                entries=(
                    SimpleNamespace(uid=3, reference=6402, level=19, caster_id=8),
                    SimpleNamespace(uid=19, reference=6402, level=3, caster_id=7),
                )
            ),
        )
        with patch(
            "wakfu_server.combat_retained_runtime.native_retained_condition_effects",
            return_value=((1, 310, 19), (2, 5, 22), (3, 310, 3)),
        ):
            carriers = ordered_registered_state_carriers(SimpleNamespace(), manager)
        self.assertEqual(carriers, ((6402, 3, 7), (6402, 19, 8)))
        self.assertEqual(self.query([self.row(0, carriers=carriers)]), 3)

    def test_missing_registration_or_manager_authority_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "population"):
            state_level_population(SimpleNamespace(), None)
        manager = SimpleNamespace(id=7, state_ledger=SimpleNamespace(entries=()))
        with patch(
            "wakfu_server.combat_retained_runtime.native_retained_condition_effects",
            return_value=((1, 310, 19),),
        ):
            with self.assertRaisesRegex(ValueError, "registered eZk"):
                ordered_registered_state_carriers(SimpleNamespace(), manager)

    def test_original_effect_expression_queries_exact_signature_and_first_level(self):
        seen = []
        context = ConditionContext(
            {
                "caster": ConditionActor(
                    actor_id=7, state_ids=frozenset(), state_levels=()
                ),
                "target": ConditionActor(
                    state_levels=((6402, 7), (6402, 19)), state_ids=frozenset()
                ),
            },
            state_max_level_query=lambda *args: seen.append(args) or 7,
        )
        self.assertTrue(
            evaluate_condition(
                '(GetStateMaxLevelCountInRange(0,30,"target",6402)==GetStateLevel(6402,"target")) and not HasState(6401,"target")',
                context,
            )
        )
        self.assertEqual(seen, [(0, 30, "target", 6402, "")])

    def test_condition_rejects_dynamic_state_reference_bad_signature_and_missing_query(
        self,
    ):
        for expression in (
            'GetStateMaxLevelCountInRange(0,30,"caster",GetLevel()) == 0',
            'GetStateMaxLevelCountInRange(0,30,"caster") == 0',
            'GetStateMaxLevelCountInRange(0,30,"caster",6402) == 0',
        ):
            with self.assertRaises(UnknownCondition):
                evaluate_condition(expression, ConditionContext({}))
