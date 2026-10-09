"""Lightweight condition/adapter area identity integration without catalogs."""
import unittest
from types import SimpleNamespace

from wakfu_server.combat_conditions import (
    ConditionContext,
    UnknownCondition,
    evaluate_condition,
)
from wakfu_server.combat_runtime_adapter import NativeServerRuntimeAdapter


class AreaPredicateIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.preview = SimpleNamespace(
            actors={1: SimpleNamespace(id=1), 2: SimpleNamespace(id=2)},
            native_effect_areas={
                101: dict(
                    uid=101,
                    reference=823,
                    native_type_id=12,
                    owner_id=2,
                    native_area_contract="faZ",
                    cell=(2, 3, 0),
                    native_cells_xy=((2, 3),),
                )
            },
        )
        self.adapter = NativeServerRuntimeAdapter.__new__(NativeServerRuntimeAdapter)
        self.adapter.actor_authority = lambda p, actor: SimpleNamespace(
            targeting={"is_eGj": True, "dpu_id": 1}
        )

    def context(self, target_id=None, cell=(2, 3, 0)):
        invocation = SimpleNamespace(caster_id=1, target_id=target_id, cell=cell)
        return ConditionContext(
            {},
            area_identity_query=lambda name, value: self.adapter._area_identity_query(
                self.preview, invocation, name, value
            ),
        )

    def test_registered_cell_area_and_literal_null_routes(self):
        for target_id, cell in ((None, (2, 3, 0)), (101, (9, 9, 0)), (None, None)):
            context = self.context(target_id, cell)
            self.assertTrue(
                evaluate_condition(
                    "IsAreaType(12) and IsSpecificArea(823) and IsOwnDeposit()", context
                )
            )
        self.assertFalse(evaluate_condition("IsAreaType(12)", self.context(1)))
        self.assertFalse(evaluate_condition("IsOwnDeposit(True)", self.context()))

    def test_missing_dpu_or_target_preserves_unknown(self):
        self.adapter.actor_authority = lambda p, actor: SimpleNamespace(
            targeting={"is_eGj": True}
        )
        with self.assertRaises(UnknownCondition):
            evaluate_condition("IsOwnDeposit()", self.context())
        with self.assertRaises(UnknownCondition):
            evaluate_condition("IsSpecificArea(823)", self.context(999))

    def test_native_argument_shapes_and_missing_query_reject(self):
        for source in (
            'IsAreaType(12, "target")',
            'IsSpecificArea(823, "caster")',
            "IsOwnDeposit(12)",
            "IsOwnDeposit(True, False)",
            "IsOwnDeposit(IsEnemy())",
        ):
            with self.subTest(source=source), self.assertRaises(UnknownCondition):
                evaluate_condition(source, self.context())
        with self.assertRaises(UnknownCondition):
            evaluate_condition("IsAreaType(12)", ConditionContext({}))

    def test_nested_qp_owner_resolves_dpu_and_cycle_is_unknown(self):
        self.preview.native_effect_areas[101]["owner_id"] = 102
        self.preview.native_effect_areas[102] = dict(
            self.preview.native_effect_areas[101], uid=102, owner_id=2
        )
        self.assertTrue(evaluate_condition("IsOwnDeposit()", self.context(101)))
        self.preview.native_effect_areas[102]["owner_id"] = 101
        with self.assertRaises(UnknownCondition):
            evaluate_condition("IsOwnDeposit()", self.context(101))


if __name__ == "__main__":
    unittest.main()
