"""Native faU deposits are actual registered Qq PVs, never actor resources."""
import unittest
from types import SimpleNamespace

import test_combat_gate_area_lifecycle as fixture
from wakfu_server.combat_area_authority import area_guards
from wakfu_server.combat_area_contracts import deposit_grade
from wakfu_server.combat_area_predicates import is_own_deposit
from wakfu_server.combat_effect_area import native_effect_areas, remove_owned_hour_area
from wakfu_server.combat_effect_area_queries import _rows
from wakfu_server.combat_original_controller import original_target_controller
from wakfu_server.combat_state_managers import registered_area_pv, state_manager


class NativeDepositAreaLifecycleTests(unittest.TestCase):
    def deposits(self):
        return [
            row
            for row in native_effect_areas().values()
            if row["type"] == "ENUTROF_DEPOSIT"
        ]

    def test_installed_deposits_create_actual_pv_grade_and_nullable_manager(self):
        factory = fixture.NativeGateAreaLifecycleTests()
        self.assertTrue(self.deposits())
        for definition in self.deposits():
            with self.subTest(reference=definition["reference"]):
                fight, handler, allocated, packets = factory.create()
                self.assertTrue(factory.invoke(handler, definition["reference"]))
                row = _rows(fight)[0]
                self.assertEqual(row["native_area_contract"], "faU")
                self.assertEqual(row["native_deposit_grade"], deposit_grade(definition))
                self.assertEqual(
                    (row["native_type_id"], row["native_obstacle_id"]), (12, -1)
                )
                pv = registered_area_pv(fight, row["uid"])
                self.assertEqual(pv.position, (2, 3, 0))
                self.assertEqual(
                    pv.native_running_effect_manager,
                    12 in definition["native_area_properties"],
                )
                if not pv.native_running_effect_manager:
                    self.assertIsNone(state_manager(fight, row["uid"]))
                    self.assertNotIn("state_ledger", row)
                self.assertEqual(
                    area_guards(fight, row["uid"]), dict(baF=True, baG=False, baK=False)
                )
                self.assertEqual(len(packets), 1)

    def test_deposit_owner_query_controller_and_removal_share_actual_uid(self):
        factory = fixture.NativeGateAreaLifecycleTests()
        fight, handler, _, _ = factory.create()
        factory.invoke(handler, self.deposits()[0]["reference"])
        self.assertTrue(
            is_own_deposit(
                fight,
                source_id=7,
                target_kind="cell",
                pv_owner_query=lambda identity: identity,
                cell=(2, 3, 99),
            )
        )
        self.assertTrue(
            is_own_deposit(
                fight,
                source_id=7,
                target_kind="cell",
                pv_owner_query=lambda identity: identity,
                cell=(2, 3, 99),
                exclude_center=True,
            )
        )
        self.assertEqual(
            original_target_controller(
                fight, lambda *args: SimpleNamespace(native_controller_id=7), 901
            ),
            7,
        )
        self.assertEqual(
            remove_owned_hour_area(fight, 901)[0]["native_area_contract"], "faU"
        )
        self.assertEqual(_rows(fight), ())

    def test_corrupted_deposit_grade_rejects_registered_pv(self):
        factory = fixture.NativeGateAreaLifecycleTests()
        fight, handler, _, _ = factory.create()
        factory.invoke(handler, self.deposits()[0]["reference"])
        fight.native_effect_areas[901]["native_deposit_grade"] += 1
        with self.assertRaisesRegex(ValueError, "grade provenance"):
            registered_area_pv(fight, 901)

    def test_deposit_actual_source_container_keeps_qq_namespace(self):
        from unittest.mock import patch
        from wakfu_server.combat_effect_dispatch import EffectInvocation
        from wakfu_server.combat_trigger_identifiers import source_identifiers

        factory = fixture.NativeGateAreaLifecycleTests()
        fight, handler, _, _ = factory.create()
        factory.invoke(handler, self.deposits()[0]["reference"])
        invocation = EffectInvocation(
            100,
            1,
            7,
            901,
            (2, 3, 0),
            native_retained_container=dict(
                present=True,
                type=3,
                id=901,
                level=1,
                is_spell=False,
                native_kind="effect_area",
            ),
        )
        retention = SimpleNamespace(
            fight=fight,
            container=lambda invocation: (
                dict(container_present=True, container_type=3),
                901,
            ),
        )
        with patch(
            "wakfu_server.combat_trigger_identifiers.zone_trigger_policies",
            return_value={"100": [400, False, True]},
        ):
            result = source_identifiers(
                retention, dict(effect_class=400, native_effect_flags=[]), invocation
            )
        self.assertEqual(result["native_container"]["type"], 3)
        self.assertFalse(result["native_container"]["is_state"])
