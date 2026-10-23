"""PostgreSQL custody, unlink and relink coverage for native companions."""
import struct
import unittest
import uuid

from postgres_case import PostgresCase
from wakfu_server import fight_store
from wakfu_server.characters import companion_equipment, companions
from wakfu_server.inventory_items import grant
from wakfu_server.inventory_items import item_proto
from wakfu_server.wire import proto_fields


class CompanionEquipmentPostgresTests(PostgresCase):
    def setUp(self):
        super().setUp()
        self.account = self.store.register(
            "companion-gear-" + uuid.uuid4().hex[:10], "local-password"
        )["id"]
        self.character = self.store.create_character(self.account, "Gear Owner")
        self.generation = self.store.begin_session(self.account)
        self.store.select_character(self.account, self.generation, self.character["id"])
        self.container = next(
            row["uid"]
            for row in self.character["inventory_containers"]
            if row["kind"] == 0
        )

    def _grant(self, ref=13601, slot=0):
        return grant(
            self.store,
            self.account,
            self.generation,
            self.character["id"],
            reference=ref,
            quantity=1,
            container=self.container,
            slot=slot,
            allowed_references={ref},
        )

    def _activate(self, slot=0):
        descriptor = next(
            row for row in companions.descriptors().values() if row["item_ref"] == 17878
        )
        item = self._grant(descriptor["item_ref"], slot)
        result = companions.use(
            self.store,
            self.account,
            self.generation,
            self.character["id"],
            struct.pack(">iq", descriptor["action_id"], item["uid"]),
            in_fight=False,
        )
        return result["companion"], descriptor

    def _save_body(self, identity, uid, slot=0):
        return struct.pack(">qhBbq", identity, 1, 1, slot, uid)

    def _owned(self, uid):
        with self.store.connection() as db:
            return db.execute(
                "SELECT * FROM inventory_items WHERE uid=%s AND character_id=%s",
                (uid, self.character["id"]),
            ).fetchone()

    def test_equip_retrieve_unlink_and_reactivate_preserves_uid_metadata_and_xp(self):
        companion, descriptor = self._activate()
        gear = self._grant(slot=1)
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO inventory_item_elements(uid,damage_elements,resistance_elements) "
                "VALUES(%s,4,8)",
                (gear["uid"],),
            )
            db.execute(
                "INSERT INTO inventory_item_bindings(uid,bound,template_reference) "
                "VALUES(%s,false,13601)",
                (gear["uid"],),
            )
            db.execute(
                "INSERT INTO inventory_item_shards(uid,shard_state) VALUES(%s,%s)",
                (gear["uid"], b"\x18\x00"),
            )
            db.execute(
                "INSERT INTO inventory_item_recycling_state(uid,unidentified,socketed) "
                "VALUES(%s,false,true)",
                (gear["uid"],),
            )
            db.execute(
                "INSERT INTO inventory_item_appearances(uid,appearance_ref) VALUES(%s,2024)",
                (gear["uid"],),
            )
            db.execute(
                "UPDATE account_companions SET xp=987654 WHERE id=%s",
                (companion["id"],),
            )

        saved = companion_equipment.save(
            self.store,
            self.account,
            self.generation,
            self.character["id"],
            self._save_body(companion["id"], gear["uid"]),
            in_fight=False,
        )
        self.assertEqual(12646, saved["packets"][2][0])
        self.assertIsNone(self._owned(gear["uid"]))
        with self.store.connection() as db:
            row = db.execute(
                "SELECT uid,entry FROM companion_equipment WHERE companion_id=%s",
                (companion["id"],),
            ).fetchone()
            self.assertEqual(gear["uid"], row["uid"])
            entry = row["entry"]
            self.assertEqual(gear["uid"], entry["item"]["uid"])
            self.assertEqual(
                4, entry["metadata"]["inventory_item_elements"]["damage_elements"]
            )
            self.assertFalse(entry["metadata"]["inventory_item_bindings"]["bound"])
            self.assertEqual(
                {"$bytes": "1800"},
                entry["metadata"]["inventory_item_shards"]["shard_state"],
            )
            self.assertEqual(
                2024, entry["metadata"]["inventory_item_appearances"]["appearance_ref"]
            )
            self.assertTrue(
                entry["metadata"]["inventory_item_recycling_state"]["socketed"]
            )

        # Native 13345 performs the same locked save plan as a full clear.
        companion_equipment.retrieve_all(
            self.store,
            self.account,
            self.generation,
            self.character["id"],
            struct.pack(">q", companion["id"]),
            in_fight=False,
        )
        restored = self._owned(gear["uid"])
        self.assertIsNotNone(restored)
        with self.store.connection() as db:
            metadata = db.execute(
                "SELECT damage_elements,resistance_elements FROM inventory_item_elements "
                "WHERE uid=%s",
                (gear["uid"],),
            ).fetchone()
            self.assertEqual(
                (4, 8), (metadata["damage_elements"], metadata["resistance_elements"])
            )
            self.assertEqual(
                b"\x18\x00",
                db.execute(
                    "SELECT shard_state FROM inventory_item_shards WHERE uid=%s",
                    (gear["uid"],),
                ).fetchone()["shard_state"],
            )
            self.assertEqual(
                2024,
                db.execute(
                    "SELECT appearance_ref FROM inventory_item_appearances WHERE uid=%s",
                    (gear["uid"],),
                ).fetchone()["appearance_ref"],
            )
            recycling = db.execute(
                "SELECT unidentified,socketed FROM inventory_item_recycling_state WHERE uid=%s",
                (gear["uid"],),
            ).fetchone()
            self.assertEqual(
                (False, True), (recycling["unidentified"], recycling["socketed"])
            )
            binding = db.execute(
                "SELECT bound,template_reference FROM inventory_item_bindings WHERE uid=%s",
                (gear["uid"],),
            ).fetchone()
            self.assertEqual(
                (False, 13601), (binding["bound"], binding["template_reference"])
            )
            self.assertEqual(
                0,
                db.execute(
                    "SELECT count(*) AS n FROM companion_equipment "
                    "WHERE companion_id=%s",
                    (companion["id"],),
                ).fetchone()["n"],
            )
            db.execute(
                "UPDATE account_companions SET xp=987654 WHERE id=%s",
                (companion["id"],),
            )

        unlinked = companion_equipment.unlink(
            self.store,
            self.account,
            self.generation,
            self.character["id"],
            struct.pack(">q", companion["id"]),
            in_fight=False,
        )
        self.assertTrue(unlinked["applied"])
        with self.store.connection() as db:
            item = db.execute(
                "SELECT i.uid,i.reference,c.xp FROM inventory_items i "
                "JOIN inventory_item_companions c USING(uid) "
                "WHERE i.character_id=%s",
                (self.character["id"],),
            ).fetchone()
            self.assertEqual(
                (descriptor["item_ref"], 987654), (item["reference"], item["xp"])
            )
            sidekick_uid = item["uid"]
        restored_companion_item = next(
            row
            for row in unlinked["character"]["inventory_items"]
            if row["uid"] == sidekick_uid
        )
        encoded_tags = [
            tag for tag, _ in proto_fields(item_proto(restored_companion_item))
        ]
        self.assertIn(434, encoded_tags)  # Native ProtoItem54 companionInfo.
        info = next(
            value
            for tag, value in proto_fields(item_proto(restored_companion_item))
            if tag == 434
        )
        self.assertEqual(987654, dict(proto_fields(info))[8])
        relink = companions.use(
            self.store,
            self.account,
            self.generation,
            self.character["id"],
            struct.pack(">iq", descriptor["action_id"], sidekick_uid),
            in_fight=False,
        )
        self.assertEqual(companion["id"], relink["companion"]["id"])
        self.assertEqual(987654, relink["companion"]["xp"])
        self.assertIsNone(self._owned(sidekick_uid))
        with self.store.connection() as db:
            self.assertEqual(
                1,
                db.execute(
                    "SELECT count(*) AS n FROM account_companions " "WHERE id=%s",
                    (companion["id"],),
                ).fetchone()["n"],
            )
            self.assertEqual(
                1,
                db.execute(
                    "SELECT count(*) AS n FROM companion_unlink_receipts "
                    "WHERE companion_id=%s",
                    (companion["id"],),
                ).fetchone()["n"],
            )

    def test_native_pet_slot_carries_full_pet_sidecar_across_custody(self):
        companion, _ = self._activate()
        pet = self._grant(ref=12128, slot=1)
        with self.store.connection() as db:
            db.execute(
                "UPDATE inventory_pets SET name='Custody Pet',xp=321,health=19,"
                "color_item_ref=12284,equipped_item_ref=12240,reskin_item_ref=12131,revision=7 "
                "WHERE uid=%s",
                (pet["uid"],),
            )
        with self.store.connection() as db:
            sidecar_before = dict(
                db.execute(
                    "SELECT * FROM inventory_pets WHERE uid=%s", (pet["uid"],)
                ).fetchone()
            )
        companion_equipment.save(
            self.store,
            self.account,
            self.generation,
            self.character["id"],
            self._save_body(companion["id"], pet["uid"], slot=22),
            in_fight=False,
        )
        with self.store.connection() as db:
            stored = db.execute(
                "SELECT uid,entry FROM companion_equipment WHERE companion_id=%s",
                (companion["id"],),
            ).fetchone()
            self.assertEqual(pet["uid"], stored["uid"])
            self.assertEqual(
                sidecar_before["xp"],
                stored["entry"]["metadata"]["inventory_pets"]["xp"],
            )
            self.assertEqual(
                sidecar_before["name"],
                stored["entry"]["metadata"]["inventory_pets"]["name"],
            )

        companion_equipment.retrieve_all(
            self.store,
            self.account,
            self.generation,
            self.character["id"],
            struct.pack(">q", companion["id"]),
            in_fight=False,
        )
        with self.store.connection() as db:
            sidecar_after = dict(
                db.execute(
                    "SELECT * FROM inventory_pets WHERE uid=%s", (pet["uid"],)
                ).fetchone()
            )
        self.assertEqual(sidecar_before, sidecar_after)

    def test_selected_native_ring_saves_projects_and_rejects_excluded_ring_atomically(
        self,
    ):
        import struct
        from wakfu_server.character_levels import XP_BY_LEVEL
        from wakfu_server.equipment import RULES
        from wakfu_server.element_selection import select as select_elements

        companion, _ = self._activate()
        # 24392 and 24408 are actual mutually exclusive ring variants. Their
        # native equipment plans qualify when their respective element masks
        # are selected through the ordinary 12487 mutation path.
        with self.store.connection() as db:
            db.execute(
                "UPDATE characters SET level=200 WHERE id=%s", (self.character["id"],)
            )
            db.execute(
                "UPDATE account_companions SET xp=%s WHERE id=%s",
                (XP_BY_LEVEL[200], companion["id"]),
            )
        first_ring = self._grant(ref=24392, slot=1)
        excluded_ring = self._grant(ref=24408, slot=2)
        first_mask, excluded_mask = 14, 6
        self.assertEqual(RULES[24392]["slots"], [7, 8])
        self.assertEqual(RULES[24408]["slots"], [7, 8])
        select_elements(
            self.store,
            self.account,
            self.generation,
            self.character["id"],
            struct.pack(">qBB", first_ring["uid"], first_mask, 0),
        )
        select_elements(
            self.store,
            self.account,
            self.generation,
            self.character["id"],
            struct.pack(">qBB", excluded_ring["uid"], excluded_mask, 0),
        )
        first_slot, excluded_slot = RULES[24392]["slots"]
        companion_equipment.save(
            self.store,
            self.account,
            self.generation,
            self.character["id"],
            self._save_body(companion["id"], first_ring["uid"], first_slot),
            in_fight=False,
        )
        self.assertIsNone(self._owned(first_ring["uid"]))
        companions.add_to_party(
            self.store,
            self.account,
            self.generation,
            self.character["id"],
            struct.pack(">q", companion["id"]),
        )
        with self.store.connection() as db:
            projected = companions.combat_sources(
                db, self.account, self.character["id"], store=self.store
            )
        self.assertEqual(len(projected), 1)
        equipped = projected[0]["equipment_entries"]
        self.assertEqual(len(equipped), 1)
        self.assertEqual(equipped[0]["entry"]["item"]["uid"], first_ring["uid"])
        self.assertEqual(equipped[0]["entry"]["item"]["damage_elements"], first_mask)
        companions.remove_from_party(
            self.store,
            self.account,
            self.generation,
            self.character["id"],
            companion["id"],
        )

        # The mutually exclusive ring still rejects after the first one is
        # reloaded from durable companion equipment; no UID/quantity is lost.
        with self.assertRaisesRegex(ValueError, "EQUIP criteria"):
            companion_equipment.save(
                self.store,
                self.account,
                self.generation,
                self.character["id"],
                self._save_body(companion["id"], excluded_ring["uid"], excluded_slot),
                in_fight=False,
            )
        self.assertEqual(self._owned(excluded_ring["uid"])["quantity"], 1)
        with self.store.connection() as db:
            saved = list(
                db.execute(
                    "SELECT uid,slot FROM companion_equipment WHERE companion_id=%s",
                    (companion["id"],),
                )
            )
            elements = db.execute(
                "SELECT damage_elements,resistance_elements FROM inventory_item_elements WHERE uid=%s",
                (excluded_ring["uid"],),
            ).fetchone()
        self.assertEqual(
            [(first_ring["uid"], first_slot)],
            [(row["uid"], row["slot"]) for row in saved],
        )
        self.assertEqual(
            (excluded_mask, 0),
            (elements["damage_elements"], elements["resistance_elements"]),
        )

    def test_empty_equipment_emblem_condition_tracks_real_companion_slots(self):
        from wakfu_server.equipment import RULES
        from wakfu_server.equipment_conditions import catalog

        companion, _ = self._activate()
        emblem = self._grant(ref=29573, slot=1)
        self.assertEqual([17], RULES[29573]["slots"])
        self.assertIn("GetEquipment(0) == -1", catalog()["29573"]["EQUIP"])

        # The native condition is true for this NPC sheet: slot17 is not one
        # of the slots queried by the original empty-equipment expression.
        companion_equipment.save(
            self.store,
            self.account,
            self.generation,
            self.character["id"],
            self._save_body(companion["id"], emblem["uid"], 17),
            in_fight=False,
        )
        self.assertIsNone(self._owned(emblem["uid"]))
        with self.store.connection() as db:
            stored = db.execute(
                "SELECT uid,slot FROM companion_equipment WHERE companion_id=%s",
                (companion["id"],),
            ).fetchall()
        self.assertEqual(
            [(emblem["uid"], 17)], [(row["uid"], row["slot"]) for row in stored]
        )

        gear = self._grant(ref=13601, slot=2)
        with self.assertRaisesRegex(ValueError, "EQUIP criteria"):
            companion_equipment.save(
                self.store,
                self.account,
                self.generation,
                self.character["id"],
                self._save_body(companion["id"], gear["uid"], 0),
                in_fight=False,
            )
        self.assertEqual(1, self._owned(gear["uid"])["quantity"])
        with self.store.connection() as db:
            stored = db.execute(
                "SELECT uid,slot FROM companion_equipment WHERE companion_id=%s",
                (companion["id"],),
            ).fetchall()
        self.assertEqual(
            [(emblem["uid"], 17)], [(row["uid"], row["slot"]) for row in stored]
        )

        companion_equipment.retrieve_all(
            self.store,
            self.account,
            self.generation,
            self.character["id"],
            struct.pack(">q", companion["id"]),
            in_fight=False,
        )
        self.assertEqual(1, self._owned(emblem["uid"])["quantity"])
        companion_equipment.save(
            self.store,
            self.account,
            self.generation,
            self.character["id"],
            self._save_body(companion["id"], gear["uid"], 0),
            in_fight=False,
        )
        self.assertIsNone(self._owned(gear["uid"]))

    def test_all_fourteen_supported_native_companion_rings_use_real_element_selection_and_roundtrip(
        self,
    ):
        import struct
        from wakfu_server.character_levels import XP_BY_LEVEL
        from wakfu_server.equipment import RULES
        from wakfu_server.element_selection import select as select_elements

        # These masks match each template's native 1068 effect count and were
        # verified through the 12487 selection contract. Resistance effects
        # are absent for these templates.
        refs_and_masks = (
            (24392, 14),
            (24408, 6),
            (24426, 6),
            (24440, 14),
            (24456, 6),
            (24473, 6),
            (24488, 14),
            (24521, 6),
            (24537, 14),
            (24552, 6),
            (24567, 14),
            (24585, 14),
            (24601, 14),
            (24615, 14),
        )
        companion, _ = self._activate()
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

        admitted = []
        for index, (reference, mask) in enumerate(refs_and_masks):
            with self.subTest(reference=reference):
                native_slots = RULES[reference]["slots"]
                self.assertEqual(native_slots, [7, 8])
                item = self._grant(ref=reference, slot=index + 1)
                selected = select_elements(
                    self.store,
                    self.account,
                    self.generation,
                    self.character["id"],
                    struct.pack(">qBB", item["uid"], mask, 0),
                )
                self.assertTrue(selected["applied"])
                self.assertEqual(
                    (mask, 0),
                    (selected["damage_elements"], selected["resistance_elements"]),
                )
                companion_equipment.save(
                    self.store,
                    self.account,
                    self.generation,
                    self.character["id"],
                    self._save_body(companion["id"], item["uid"], native_slots[0]),
                    in_fight=False,
                )
                self.assertIsNone(self._owned(item["uid"]))

                # roster() rehydrates companion equipment from PostgreSQL;
                # this is the same path used after reconnect/combat setup.
                with self.store.connection() as db:
                    projected = companions.combat_sources(
                        db, self.account, self.character["id"], store=self.store
                    )
                self.assertEqual(len(projected), 1)
                source = projected[0]
                entries = source["equipment_entries"]
                self.assertEqual(1, len(entries))
                restored_item = entries[0]["entry"]["item"]
                self.assertEqual(
                    (item["uid"], reference, mask),
                    (
                        restored_item["uid"],
                        restored_item["reference"],
                        restored_item["damage_elements"],
                    ),
                )
                self.assertTrue(source["equipment_stat_bonuses"])
                self.assertTrue(
                    any(
                        identity in source["equipment_stat_bonuses"]
                        for identity in (21, 22, 23)
                    )
                )

                companion_equipment.retrieve_all(
                    self.store,
                    self.account,
                    self.generation,
                    self.character["id"],
                    struct.pack(">q", companion["id"]),
                    in_fight=False,
                )
                returned = self._owned(item["uid"])
                self.assertEqual(1, returned["quantity"])
                with self.store.connection() as db:
                    element_state = db.execute(
                        "SELECT damage_elements,resistance_elements FROM inventory_item_elements WHERE uid=%s",
                        (item["uid"],),
                    ).fetchone()
                self.assertEqual(
                    (mask, 0),
                    (
                        element_state["damage_elements"],
                        element_state["resistance_elements"],
                    ),
                )
                admitted.append(reference)

        self.assertEqual(
            tuple(reference for reference, _ in refs_and_masks), tuple(admitted)
        )

    def test_three_native_negative_wp_rings_project_restore_and_keep_mutual_exclusion(
        self,
    ):
        import struct
        from wakfu_server.character_levels import XP_BY_LEVEL
        from wakfu_server.equipment import RULES
        from wakfu_server.element_selection import select as select_elements

        references = (19698, 22226, 22227)
        companion, _ = self._activate()
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
        with self.store.connection() as db:
            baseline = companions.combat_sources(
                db, self.account, self.character["id"], store=self.store
            )[0]
        self.assertEqual((6, 6), (baseline["wp"], baseline["max_wp"]))

        items = {}
        for index, reference in enumerate(references):
            with self.subTest(reference=reference):
                item = self._grant(ref=reference, slot=index + 1)
                items[reference] = item
                selected = select_elements(
                    self.store,
                    self.account,
                    self.generation,
                    self.character["id"],
                    struct.pack(">qBB", item["uid"], 14, 0),
                )
                self.assertEqual(
                    (14, 0),
                    (selected["damage_elements"], selected["resistance_elements"]),
                )
                slot = RULES[reference]["slots"][0]
                companion_equipment.save(
                    self.store,
                    self.account,
                    self.generation,
                    self.character["id"],
                    self._save_body(companion["id"], item["uid"], slot),
                    in_fight=False,
                )
                self.assertIsNone(self._owned(item["uid"]))
                with self.store.connection() as db:
                    projected = companions.combat_sources(
                        db, self.account, self.character["id"], store=self.store
                    )[0]
                self.assertEqual((4, 4), (projected["wp"], projected["max_wp"]))
                self.assertEqual(-2, projected["equipment_stat_bonuses"][4])
                self.assertEqual(
                    item["uid"],
                    projected["equipment_entries"][0]["entry"]["item"]["uid"],
                )

                companion_equipment.retrieve_all(
                    self.store,
                    self.account,
                    self.generation,
                    self.character["id"],
                    struct.pack(">q", companion["id"]),
                    in_fight=False,
                )
                self.assertEqual(1, self._owned(item["uid"])["quantity"])
                with self.store.connection() as db:
                    elements = db.execute(
                        "SELECT damage_elements,resistance_elements FROM inventory_item_elements WHERE uid=%s",
                        (item["uid"],),
                    ).fetchone()
                self.assertEqual(
                    (14, 0),
                    (elements["damage_elements"], elements["resistance_elements"]),
                )
                with self.store.connection() as db:
                    restored = companions.combat_sources(
                        db, self.account, self.character["id"], store=self.store
                    )[0]
                self.assertEqual((6, 6), (restored["wp"], restored["max_wp"]))
                self.assertFalse(restored["equipment_entries"])

        # 19698 and 22226 are a native mutually exclusive pair. Keep 19698
        # durable in companion storage while trying the rejected second ring.
        first = items[19698]
        second = items[22226]
        slot = RULES[19698]["slots"][0]
        companion_equipment.save(
            self.store,
            self.account,
            self.generation,
            self.character["id"],
            self._save_body(companion["id"], first["uid"], slot),
            in_fight=False,
        )
        with self.assertRaisesRegex(ValueError, "EQUIP criteria"):
            companion_equipment.save(
                self.store,
                self.account,
                self.generation,
                self.character["id"],
                self._save_body(
                    companion["id"], second["uid"], RULES[22226]["slots"][1]
                ),
                in_fight=False,
            )
        self.assertIsNotNone(self._owned(second["uid"]))
        with self.store.connection() as db:
            stored = db.execute(
                "SELECT uid,slot FROM companion_equipment WHERE companion_id=%s",
                (companion["id"],),
            ).fetchall()
        self.assertEqual(
            [(first["uid"], slot)], [(row["uid"], row["slot"]) for row in stored]
        )
        with self.store.connection() as db:
            projected = companions.combat_sources(
                db, self.account, self.character["id"], store=self.store
            )[0]
        self.assertEqual((4, 4), (projected["wp"], projected["max_wp"]))

    def test_retrieve_capacity_failure_and_stale_foreign_combat_guards_are_atomic(self):
        companion, _ = self._activate()
        gear = self._grant(slot=1)
        companion_equipment.save(
            self.store,
            self.account,
            self.generation,
            self.character["id"],
            self._save_body(companion["id"], gear["uid"]),
            in_fight=False,
        )

        # Fill every eligible character bag, so retrieval cannot place the
        # item. The rejected transaction must keep custody.
        with self.store.connection() as db:
            bags = [
                dict(row)
                for row in db.execute(
                    "SELECT * FROM inventory_containers WHERE character_id=%s AND kind IN (0,1,2,3)",
                    (self.character["id"],),
                )
            ]
            occupied = {
                (row["container"], row["slot"])
                for row in db.execute(
                    "SELECT container,slot FROM inventory_items WHERE character_id=%s",
                    (self.character["id"],),
                )
            }
        for bag in bags:
            for slot in range(bag["capacity"]):
                if (bag["uid"], slot) in occupied:
                    continue
                grant(
                    self.store,
                    self.account,
                    self.generation,
                    self.character["id"],
                    reference=13601,
                    quantity=1,
                    container=bag["uid"],
                    slot=slot,
                    allowed_references={13601},
                )
        with self.assertRaises(ValueError):
            companion_equipment.retrieve_all(
                self.store,
                self.account,
                self.generation,
                self.character["id"],
                struct.pack(">q", companion["id"]),
                in_fight=False,
            )
        self.assertIsNone(self._owned(gear["uid"]))
        with self.store.connection() as db:
            self.assertEqual(
                1,
                db.execute(
                    "SELECT count(*) AS n FROM companion_equipment "
                    "WHERE companion_id=%s AND uid=%s",
                    (companion["id"], gear["uid"]),
                ).fetchone()["n"],
            )

        with self.assertRaises(ValueError):
            companion_equipment.retrieve_all(
                self.store,
                self.account,
                "stale-generation",
                self.character["id"],
                struct.pack(">q", companion["id"]),
                in_fight=False,
            )
        with self.assertRaises(ValueError):
            companion_equipment.retrieve_all(
                self.store,
                self.account,
                self.generation,
                self.character["id"],
                struct.pack(">q", companion["id"]),
                in_fight=True,
            )
        with self.assertRaises(ValueError):
            companion_equipment.save(
                self.store,
                self.account,
                self.generation,
                self.character["id"],
                self._save_body(companion["id"], gear["uid"], slot=3),
                in_fight=False,
            )

        foreign = self.store.register(
            "foreign-" + uuid.uuid4().hex[:10], "local-password"
        )["id"]
        foreign_character = self.store.create_character(foreign, "Foreign Owner")
        foreign_generation = self.store.begin_session(foreign)
        self.store.select_character(
            foreign, foreign_generation, foreign_character["id"]
        )
        with self.assertRaises(ValueError):
            companion_equipment.retrieve_all(
                self.store,
                foreign,
                foreign_generation,
                foreign_character["id"],
                struct.pack(">q", companion["id"]),
                in_fight=False,
            )

        companions.add_to_party(
            self.store,
            self.account,
            self.generation,
            self.character["id"],
            struct.pack(">q", companion["id"]),
        )
        fight_id = fight_store.create(
            self.store, self.account, self.generation, self.character["id"], team=0
        )
        with self.store.connection() as db:
            companions.enroll(
                db,
                fight_id,
                companion["id"],
                self.account,
                self.character["id"],
                self.generation,
                0,
            )
            db.execute(
                "UPDATE combat_fights SET status='active' WHERE id=%s", (fight_id,)
            )
        with self.assertRaisesRegex(ValueError, "combate"):
            companion_equipment.retrieve_all(
                self.store,
                self.account,
                self.generation,
                self.character["id"],
                struct.pack(">q", companion["id"]),
                in_fight=False,
            )


if __name__ == "__main__":
    unittest.main()
