"""Focused real-catalog companion sword + partner equipment projection."""
import struct
import unittest
import uuid

from postgres_case import PostgresCase
from wakfu_server.characters import companion_equipment, companions
from wakfu_server.element_selection import select as select_elements
from wakfu_server.inventory_items import grant


class CompanionSwordEffectsPostgresTests(PostgresCase):
    def setUp(self):
        super().setUp()
        self.account = self.store.register(
            "companion-sword-" + uuid.uuid4().hex[:10], "local-password"
        )["id"]
        self.character = self.store.create_character(self.account, "Sword Owner")
        self.generation = self.store.begin_session(self.account)
        self.store.select_character(self.account, self.generation, self.character["id"])
        self.container = next(
            row["uid"]
            for row in self.character["inventory_containers"]
            if row["kind"] == 0
        )

    def _grant(self, reference, slot):
        return grant(
            self.store,
            self.account,
            self.generation,
            self.character["id"],
            reference=reference,
            quantity=1,
            container=self.container,
            slot=slot,
            allowed_references={reference},
        )

    def _owned(self, uid):
        with self.store.connection() as db:
            return db.execute(
                "SELECT uid,reference,quantity FROM inventory_items "
                "WHERE uid=%s AND character_id=%s",
                (uid, self.character["id"]),
            ).fetchone()

    @staticmethod
    def _equipment_change(identity, entries):
        body = bytearray(struct.pack(">qh", identity, len(entries)))
        for slot, uid in entries:
            body.extend(struct.pack(">Bbq", 1, slot, uid))
        return bytes(body)

    def test_four_native_sword_pairs_select_project_retrieve_and_reject_bag_only_partner(
        self,
    ):
        from wakfu_server.character_levels import XP_BY_LEVEL
        from wakfu_server.equipment import RULES

        descriptor = next(
            row for row in companions.descriptors().values() if row["item_ref"] == 17878
        )
        activation = self._grant(descriptor["item_ref"], 0)
        companion = companions.use(
            self.store,
            self.account,
            self.generation,
            self.character["id"],
            struct.pack(">iq", descriptor["action_id"], activation["uid"]),
            in_fight=False,
        )["companion"]
        with self.store.connection() as db:
            db.execute(
                "UPDATE characters SET level=245 WHERE id=%s", (self.character["id"],)
            )
            db.execute(
                "UPDATE account_companions SET xp=%s WHERE id=%s",
                (XP_BY_LEVEL[245], companion["id"]),
            )
        companions.add_to_party(
            self.store,
            self.account,
            self.generation,
            self.character["id"],
            struct.pack(">q", companion["id"]),
        )

        cases = (
            (26494, 26575, 6, (21, 22), 427),
            (26495, 26576, 6, (21, 22), 366),
            (26496, 26577, 14, (21, 22, 23), 353),
            (26497, 26578, 6, (21, 22), 573),
        )
        for index, (sword_ref, partner_ref, mask, mastery_ids, expected) in enumerate(
            cases
        ):
            with self.subTest(sword=sword_ref, partner=partner_ref):
                sword = self._grant(sword_ref, index * 2 + 1)
                partner = self._grant(partner_ref, index * 2 + 2)
                self.assertEqual([15], RULES[sword_ref]["slots"])
                self.assertEqual([7, 8], RULES[partner_ref]["slots"])
                selected = select_elements(
                    self.store,
                    self.account,
                    self.generation,
                    self.character["id"],
                    struct.pack(">qBB", sword["uid"], mask, 0),
                )
                self.assertTrue(selected["applied"])
                self.assertEqual(
                    (mask, 0),
                    (selected["damage_elements"], selected["resistance_elements"]),
                )

                # The native HasEquipmentId requirement is about equipped
                # slots, not a duplicate sitting in the owner's inventory.
                with self.assertRaisesRegex(ValueError, "EQUIP criteria"):
                    companion_equipment.save(
                        self.store,
                        self.account,
                        self.generation,
                        self.character["id"],
                        self._equipment_change(companion["id"], [(15, sword["uid"])]),
                        in_fight=False,
                    )
                self.assertEqual(1, self._owned(sword["uid"])["quantity"])
                with self.store.connection() as db:
                    self.assertEqual(
                        0,
                        db.execute(
                            "SELECT count(*) AS n FROM companion_equipment WHERE companion_id=%s",
                            (companion["id"],),
                        ).fetchone()["n"],
                    )

                companion_equipment.save(
                    self.store,
                    self.account,
                    self.generation,
                    self.character["id"],
                    self._equipment_change(
                        companion["id"],
                        [
                            (15, sword["uid"]),
                            (7, partner["uid"]),
                        ],
                    ),
                    in_fight=False,
                )
                self.assertIsNone(self._owned(sword["uid"]))
                self.assertIsNone(self._owned(partner["uid"]))
                with self.store.connection() as db:
                    sources = companions.combat_sources(
                        db, self.account, self.character["id"], store=self.store
                    )
                self.assertEqual(1, len(sources))
                source = sources[0]
                self.assertEqual(
                    expected,
                    source["equipment_stat_bonuses"][mastery_ids[0]],
                )
                for mastery in mastery_ids[1:]:
                    self.assertEqual(
                        expected, source["equipment_stat_bonuses"][mastery]
                    )
                entries = {
                    row["slot"]: row["entry"]["item"]
                    for row in source["equipment_entries"]
                }
                self.assertEqual(
                    (sword["uid"], sword_ref, mask),
                    (
                        entries[15]["uid"],
                        entries[15]["reference"],
                        entries[15]["damage_elements"],
                    ),
                )
                self.assertEqual(
                    (partner["uid"], partner_ref, 1),
                    (
                        entries[7]["uid"],
                        entries[7]["reference"],
                        entries[7]["quantity"],
                    ),
                )

                companion_equipment.retrieve_all(
                    self.store,
                    self.account,
                    self.generation,
                    self.character["id"],
                    struct.pack(">q", companion["id"]),
                    in_fight=False,
                )
                self.assertEqual(
                    (sword["uid"], 1),
                    (
                        self._owned(sword["uid"])["uid"],
                        self._owned(sword["uid"])["quantity"],
                    ),
                )
                self.assertEqual(
                    (partner["uid"], 1),
                    (
                        self._owned(partner["uid"])["uid"],
                        self._owned(partner["uid"])["quantity"],
                    ),
                )
                with self.store.connection() as db:
                    masks = db.execute(
                        "SELECT damage_elements,resistance_elements FROM inventory_item_elements "
                        "WHERE uid=%s",
                        (sword["uid"],),
                    ).fetchone()
                self.assertEqual(
                    (mask, 0), (masks["damage_elements"], masks["resistance_elements"])
                )

    def test_real_level_gear_cannot_be_newly_saved_above_its_native_criterion(self):
        from wakfu_server.character_levels import XP_BY_LEVEL
        from wakfu_server.equipment import RULES

        descriptor = next(
            row for row in companions.descriptors().values() if row["item_ref"] == 17878
        )
        activation = self._grant(descriptor["item_ref"], 0)
        companion = companions.use(
            self.store,
            self.account,
            self.generation,
            self.character["id"],
            struct.pack(">iq", descriptor["action_id"], activation["uid"]),
            in_fight=False,
        )["companion"]
        with self.store.connection() as db:
            db.execute(
                "UPDATE characters SET level=31 WHERE id=%s", (self.character["id"],)
            )
            db.execute(
                "UPDATE account_companions SET xp=%s WHERE id=%s",
                (XP_BY_LEVEL[31], companion["id"]),
            )
        item = self._grant(14891, 1)

        with self.assertRaisesRegex(ValueError, "EQUIP criteria"):
            companion_equipment.save(
                self.store,
                self.account,
                self.generation,
                self.character["id"],
                self._equipment_change(
                    companion["id"], [(RULES[14891]["slots"][0], item["uid"])]
                ),
                in_fight=False,
            )
        self.assertEqual(
            (item["uid"], 14891, 1),
            (
                self._owned(item["uid"])["uid"],
                self._owned(item["uid"])["reference"],
                self._owned(item["uid"])["quantity"],
            ),
        )
        with self.store.connection() as db:
            self.assertEqual(
                0,
                db.execute(
                    "SELECT count(*) AS n FROM companion_equipment WHERE companion_id=%s",
                    (companion["id"],),
                ).fetchone()["n"],
            )


if __name__ == "__main__":
    unittest.main()
