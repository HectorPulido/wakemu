"""Recovered empty native equipment templates stay empty in combat planning."""

import importlib
import unittest

from postgres_case import PostgresCase
from wakfu_server.combat.combat_equipment_initialization import plan
from wakfu_server.equipment import RULES
from wakfu_server.items.empty_equipment_effects import definitions
from wakfu_server.wire import proto_field


class EmptyTemplatePlanningTests(unittest.TestCase):
    def test_all_recovered_empty_templates_plan_no_effects(self):
        rows = definitions()
        self.assertEqual(len(rows), 626)
        character_id = 77
        character = {
            "id": character_id,
            "level": 245,
            "real_level": 245,
            "active_build_index": 0,
            "builds": {
                0: {
                    "equipment": "",
                    "sheet": (proto_field(8, 0) + proto_field(24, 245)).hex(),
                }
            },
            "inventory_items": [],
        }

        for reference, recovered in rows.items():
            with self.subTest(reference=reference):
                rule = RULES[reference]
                for key in (
                    "minimum_level",
                    "native_dte",
                    "slots",
                    "occupied_slots",
                    "has_conditions",
                ):
                    self.assertEqual(rule[key], recovered[key], key)
                self.assertEqual(recovered["effects"], [])
                slot = rule["slots"][0]
                uid = 1_000_000 + reference
                character["inventory_items"] = [
                    {
                        "uid": uid,
                        "reference": reference,
                        "character_id": character_id,
                        "quantity": 1,
                    }
                ]
                selected = [{"uid": uid, "slot": slot, "_level_ineligible": False}]
                self.assertEqual(
                    plan(character, templates={}, _selected_entries=selected),
                    (),
                )


class EmptyTemplatePlanningPostgresTests(PostgresCase):
    def test_real_empty_equipment_survives_ready_and_cycle(self):
        reference = 2396
        values = importlib.import_module(
            "test_equipment_null_carrier_pipeline"
        ).EquipmentNullCarrierPipelineTests._fixture(
            self, reference=reference, slot=7, level=245
        )
        character, _monster, _deck, _rng, runtime, _stats = values
        owner = character["id"]
        self.assertEqual(runtime.fight.current.id, owner)
        gear = next(
            row for row in character["inventory_items"] if row["reference"] == reference
        )
        equipped = plan(character, ordinary_only=True, templates={})
        self.assertEqual(equipped, ())
        with self.store.connection() as db:
            durable = db.execute(
                "SELECT reference, quantity FROM inventory_items WHERE uid=%s AND character_id=%s",
                (gear["uid"], owner),
            ).fetchone()
        self.assertEqual((durable["reference"], durable["quantity"]), (reference, 1))
        self.assertFalse(
            any(
                row.get("native_retained_container", {}).get("id") == reference
                for row in runtime.fight.owned_stat_effects.values()
            )
        )
