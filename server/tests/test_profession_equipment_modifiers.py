"""Exact profession equipment roots and authoritative job-action modifiers."""
import copy
import unittest
from unittest.mock import patch

from postgres_case import PostgresCase
from wakfu_server import profession_equipment_modifiers as equipment
from wakfu_server.equipment_stats import CATALOG
from wakfu_server.equipment import RULES
from wakfu_server.inventory_items import grant
from wakfu_server.wire import proto_field
from wakfu_server.profession_consumable_modifiers import (
    modifiers,
    duration_ms,
    collected_quantity,
)


def character_with(reference, *, level=245):
    item = dict(uid=101, reference=reference, character_id=7, quantity=1)
    blob = proto_field(
        10, proto_field(8, 101) + proto_field(16, RULES[reference]["slots"][0])
    )
    return dict(
        id=7,
        account_id=3,
        breed=8,
        level=level,
        effective_level=level,
        inventory_items=[item],
        builds={0: dict(equipment=blob.hex(), aptitudes="")},
    )


class ProfessionEquipmentModifierTests(unittest.TestCase):
    def test_complete_native_family_has_no_fabricated_combat_stat(self):
        roots = 0
        for reference, rows in equipment.definitions().items():
            for identity, row in rows.items():
                effect = row["equipment_effect"]
                self.assertTrue(
                    equipment.passive_profession_effect(effect, int(reference))
                )
                self.assertEqual(row["native_root"]["parameters"], effect["params"])
                self.assertEqual(row["native_root"]["effect_class"], effect["generic"])
                self.assertEqual(effect["stat_id"], -1)
                roots += 1
                invalid = copy.deepcopy(effect)
                invalid["has_triggers"] = True
                self.assertFalse(
                    equipment.passive_profession_effect(invalid, int(reference))
                )
        self.assertEqual(roots, 62)
        self.assertFalse(
            equipment.passive_profession_effect(CATALOG[2292]["effects"][0], 999999)
        )

    def test_scopes_neo_and_pet_level_use_original_parameters(self):
        def selected(*args, **kwargs):
            return dict(entries=[dict(uid=101, slot=17)])

        with patch("wakfu_server.equipment.resolve_sheet", selected):
            self.assertEqual(
                equipment.aggregate(character_with(2292), 64)["collect_quantity"], 10
            )
            self.assertEqual(
                equipment.aggregate(character_with(2292), 73)["collect_quantity"], 0
            )
            self.assertEqual(
                equipment.aggregate(character_with(10559), 40)["craft_speed"], 20
            )
            xp = equipment.aggregate(character_with(5002), 64)
            self.assertEqual(
                (xp["craft_xp"], xp["collect_xp"], xp["plant_xp"]), (1000, 1000, 0)
            )
            self.assertEqual(
                equipment.aggregate(character_with(2895), 64)["plant_probability"], 1000
            )
            neo_ref = next(
                int(ref)
                for ref, rows in equipment.definitions().items()
                if any(r["native_root"]["criterion_raw"] for r in rows.values())
            )
            self.assertEqual(
                equipment.aggregate(character_with(neo_ref), 64, is_neo_server=False)[
                    "collect_quantity"
                ],
                0,
            )
            self.assertEqual(
                equipment.aggregate(character_with(neo_ref), 64, is_neo_server=True)[
                    "collect_quantity"
                ],
                50,
            )
            with self.assertRaisesRegex(ValueError, "Neo context"):
                equipment.aggregate(character_with(neo_ref), 64)
            pet_ref = next(
                ref
                for ref, template in CATALOG.items()
                if any(
                    e.get("runner") == "eXx" and e["params"][1] > 0
                    for e in template["effects"]
                )
            )
            char = character_with(pet_ref)
            char["inventory_items"][0]["pet"] = dict(
                health=20, xp=200, xp_per_level=10, maximum_level=50
            )
            effect = next(
                e for e in CATALOG[pet_ref]["effects"] if e["runner"] == "eXx"
            )
            from wakfu_server.combat_parameters import parameter_value

            profession = (
                64
                if effect["parameter_count"] == 1
                else parameter_value(effect["params"], 1, 20)
            )
            values = equipment.aggregate(char, profession)
            self.assertEqual(
                values[equipment.KINDS[effect["generic"]]],
                parameter_value(effect["params"], 0, 20),
            )
            char["inventory_items"][0]["pet"].update(sleep_item_ref=1, sleep_date=1)
            self.assertEqual(
                equipment.aggregate(char, profession)["collect_quantity"], 0
            )


class ProfessionEquipmentPostgresTests(PostgresCase):
    def test_equipment_modifiers_reach_real_craft_and_gathering_consumers(self):
        account = self.store.register("professiongear", "local-password")["id"]
        character = self.store.create_character(account, "Profession Gear")
        generation = self.store.begin_session(account)
        self.store.select_character(account, generation, character["id"])
        with self.store.connection() as db:
            for profession in (40, 64, 73):
                db.execute(
                    "INSERT INTO account_professions(account_id,profession_id,xp) VALUES(%s,%s,1000000)",
                    (account, profession),
                )
        character = self.store.character(account, character["id"])
        container = next(
            row["uid"] for row in character["inventory_containers"] if row["kind"] == 0
        )
        for slot, reference, profession, kind, amount in (
            (0, 10559, 40, "craft_speed", 20),
            (1, 2292, 64, "collect_quantity", 10),
        ):
            item = grant(
                self.store,
                account,
                generation,
                character["id"],
                reference=reference,
                quantity=1,
                container=container,
                slot=slot,
                allowed_references={reference},
            )
            blob = proto_field(
                10,
                proto_field(8, item["uid"])
                + proto_field(16, RULES[reference]["slots"][0]),
            )
            with self.store.connection() as db:
                db.execute(
                    "INSERT INTO character_builds(character_id,build_index,sheet,equipment,deck,aptitudes) VALUES(%s,0,''::bytea,%s,''::bytea,''::bytea) ON CONFLICT(character_id,build_index) DO UPDATE SET equipment=EXCLUDED.equipment",
                    (character["id"], blob),
                )
                values = modifiers(
                    self.store, db, character["id"], profession, generation=generation
                )
                self.assertEqual(values[kind], amount)
                self.assertEqual(
                    modifiers(
                        self.store, db, character["id"], 73, generation=generation
                    )[kind],
                    0,
                )
            if kind == "craft_speed":
                from wakfu_server.crafting import craft_duration_ms

                self.assertEqual(craft_duration_ms(3000, 1, values[kind]), 2500)
            else:
                self.assertEqual(
                    collected_quantity(
                        10, values[kind], operation="native-equipment-yield"
                    ),
                    11,
                )
        with self.store.connection() as db:
            db.execute(
                "UPDATE character_builds SET equipment=''::bytea WHERE character_id=%s AND build_index=0",
                (character["id"],),
            )
            self.assertEqual(
                modifiers(self.store, db, character["id"], 64, generation=generation)[
                    "collect_quantity"
                ],
                0,
            )
