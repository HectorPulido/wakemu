"""Existing actor-dependent equipment disables safely; new admission stays strict."""
from copy import deepcopy
from unittest import TestCase
from unittest.mock import patch

from wakfu_server import equipment, equipment_conditions, builds
from wakfu_server.wire import proto_field


class EquipmentActorReconciliationTests(TestCase):
    def actor(self):
        return dict(
            id=1,
            level=100,
            breed=1,
            account_is_admin=False,
            inventory_items=[dict(uid=10, character_id=1, quantity=1, reference=999)],
            equipment_criterion_context=dict(
                actor_kind="player",
                level=100,
                real_level=100,
                breed_id=1,
                is_admin=False,
                wakfu_gauge=35,
            ),
        )

    def sheet(self):
        return proto_field(10, proto_field(8, 10) + proto_field(16, 0))

    def authority(self, criterion):
        return (
            patch.object(
                equipment,
                "RULES",
                {999: dict(slots=[0], occupied_slots=[], minimum_level=0)},
            ),
            patch.object(
                equipment_conditions,
                "catalog",
                return_value={"999": dict(EQUIP=criterion)},
            ),
        )

    def test_class_change_disables_existing_equipment_without_projection_or_uid_loss(
        self,
    ):
        actor, blob = self.actor(), self.sheet()
        first, second = self.authority('IsBreed("FECA")')
        with first, second, patch(
            "wakfu_server.equipment_eligibility._projection",
            side_effect=AssertionError(
                "Pure actor predicate must not project unknown passives"
            ),
        ):
            self.assertEqual(
                equipment.validate_sheet(actor, blob), [dict(uid=10, slot=0)]
            )
            actor["breed"] = 2
            before = deepcopy(actor)
            self.assertEqual(equipment.resolve_sheet(actor, blob)["entries"], [])
            self.assertEqual(equipment.validate_sheet(actor, blob, strict=False), [])
            self.assertEqual(actor, before)
            with self.assertRaisesRegex(ValueError, "EQUIP criteria"):
                equipment.validate_sheet(actor, blob)
            actor["breed"] = 1
            self.assertEqual(
                equipment.validate_sheet(actor, blob, strict=False),
                [dict(uid=10, slot=0)],
            )

    def test_ecology_threshold_change_filters_existing_sheet_and_preserves_owned_source(
        self,
    ):
        actor, blob = self.actor(), self.sheet()
        first, second = self.authority("GetWakfuGauge() >= 30")
        with first, second, patch(
            "wakfu_server.equipment_eligibility._projection",
            side_effect=AssertionError(
                "Pure gauge predicate must not project unknown passives"
            ),
        ):
            self.assertEqual(
                equipment.resolve_sheet(actor, blob)["entries"], [dict(uid=10, slot=0)]
            )
            actor["equipment_criterion_context"]["wakfu_gauge"] = 29
            before = deepcopy(actor)
            self.assertEqual(equipment.resolve_sheet(actor, blob)["entries"], [])
            with self.assertRaisesRegex(ValueError, "EQUIP criteria"):
                equipment.validate_sheet(actor, blob, strict=True)
            self.assertEqual(actor, before)
            actor["equipment_criterion_context"]["wakfu_gauge"] = 30
            self.assertEqual(
                equipment.resolve_sheet(actor, blob)["entries"], [dict(uid=10, slot=0)]
            )

    def test_build_save_explicitly_keeps_new_equipment_admission_strict(self):
        actor = self.actor()
        actor["breed"] = 2
        record = dict(
            sheet=b"".join(
                proto_field(tag, value)
                for tag, value in ((8, 0), (18, b"Main"), (24, (1 << 64) - 1), (56, 0))
            ),
            equipment=self.sheet(),
            deck=b"",
            aptitudes=b"",
        )
        first, second = self.authority('IsBreed("FECA")')
        with first, second, patch.object(builds, "validate_capacity"):
            with self.assertRaisesRegex(ValueError, "EQUIP criteria"):
                builds.validate(actor, 0, record)
        self.assertEqual(actor["inventory_items"][0]["uid"], 10)
