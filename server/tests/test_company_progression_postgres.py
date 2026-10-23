"""Owned native company score follows real character and companion progress."""
import struct
import uuid

from postgres_case import PostgresCase
from wakfu_server import builds, wire
from wakfu_server import companions, heroes
from wakfu_server.company_authority import CompanySnapshot, load as load_company
from wakfu_server.item_progression import award_item_xp
from wakfu_server.character_levels import XP_BY_LEVEL
from wakfu_server.equipment import RULES
from wakfu_server.inventory_items import grant


class CompanyProgressionPostgresTests(PostgresCase):
    def _actor(self, account, name):
        return self.store.create_character(account, name, breed=8)

    def _set_real_level(self, character_id, level):
        with self.store.connection() as db:
            db.execute(
                "UPDATE characters SET level=%s WHERE id=%s", (level, character_id)
            )
            db.execute(
                "UPDATE character_progression SET xp=%s WHERE character_id=%s",
                (XP_BY_LEVEL[level], character_id),
            )

    @staticmethod
    def _company(character):
        record = character["equipment_criterion_context"]["company_snapshot"]
        return CompanySnapshot.from_record(record)

    def _owned_main(self, account, character):
        with self.store.connection() as db:
            return self.store.character(account, character["id"], db)

    def _save_costume(self, account, generation, character, uid, index):
        return self.store.save_build(
            account,
            generation,
            character["id"],
            index,
            dict(
                sheet=b"".join(
                    wire.proto_field(tag, value)
                    for tag, value in (
                        (8, index),
                        (18, b"Company rank"),
                        (24, 35),
                        (56, 0),
                    )
                ),
                equipment=wire.proto_field(
                    10, wire.proto_field(8, uid) + wire.proto_field(16, 23)
                ),
                deck=b"",
                aptitudes=b"",
            ),
        )

    def _save_empty(self, account, generation, character, index):
        return self.store.save_build(
            account,
            generation,
            character["id"],
            index,
            dict(
                sheet=b"".join(
                    wire.proto_field(tag, value)
                    for tag, value in (
                        (8, index),
                        (18, b"Company rank"),
                        (24, 35),
                        (56, 0),
                    )
                ),
                equipment=builds.EMPTY_EQUIPMENT,
                deck=b"",
                aptitudes=b"",
            ),
        )

    def test_rank_threshold_uses_owned_real_levels_and_survives_hero_deletion(self):
        account = self.store.register(
            "company-rank-" + uuid.uuid4().hex[:10], "local-password"
        )["id"]
        main = self._actor(account, "Company Main")
        hero = self._actor(account, "Company Hero")
        self._set_real_level(main["id"], 245)
        self._set_real_level(hero["id"], 21)
        generation = self.store.begin_session(account)
        self.store.select_character(account, generation, main["id"])
        heroes.add(self.store, account, generation, main["id"], hero["id"])
        # Effective build level35 is intentionally below persisted real level245.
        self._save_empty(account, generation, main, 0)

        # Native score is 3 * (245 + 21) = 798 (rank 4). A lower selected
        # build level does not replace either character's real progression.
        current = self._owned_main(account, main)
        snapshot = self._company(current)
        self.assertEqual((snapshot.score, snapshot.rank), (798, 4))
        self.assertLess(current["effective_level"], current["level"])
        source = grant(
            self.store,
            account,
            generation,
            main["id"],
            reference=19543,
            quantity=1,
            container=next(
                row["uid"]
                for row in current["inventory_containers"]
                if row["kind"] == 0
            ),
            slot=0,
            allowed_references={19543},
        )
        self.assertIn(23, RULES[19543]["slots"])
        with self.assertRaisesRegex(ValueError, "EQUIP criteria"):
            self._save_costume(account, generation, main, source["uid"], 1)

        # Cross the native company threshold through the real character XP
        # progression helper; no effective/build level is used for the score.
        with self.store.connection() as db:
            db.execute("SELECT id FROM accounts WHERE id=%s FOR UPDATE", (account,))
            self.store.lock_character(
                db, account, generation, hero["id"], selected=False
            )
            award_item_xp(
                self.store,
                db,
                account,
                generation,
                hero["id"],
                XP_BY_LEVEL[22] - XP_BY_LEVEL[21],
            )
        current = self._owned_main(account, main)
        snapshot = self._company(current)
        self.assertEqual((snapshot.score, snapshot.rank), (801, 5))
        opcode, packet = snapshot.packet()
        self.assertEqual(opcode, 13873)
        self.assertEqual(struct.unpack(">IIqqiqIiB", packet)[7], 801)
        from wakfu_server.social import company as company_payload

        self.assertEqual(company_payload(account, current), packet[8:])
        self._save_costume(account, generation, main, source["uid"], 1)
        reopened = self.reopen().character(account, main["id"])
        self.assertEqual(self._company(reopened).score, 801)
        self.assertEqual(
            next(
                row["uid"]
                for row in reopened["inventory_items"]
                if row["reference"] == 19543
            ),
            source["uid"],
        )

        # Deleting the owned hero uses the public selection/deletion lifecycle;
        # the old hero's earned levels stop contributing after reconnect.
        self.store.clear_character(account, generation)
        self.store.delete_character(account, generation, hero["id"])
        self.store.select_character(account, generation, main["id"])
        reopened = self.reopen().character(account, main["id"])
        self.assertEqual(self._company(reopened).score, 735)
        with self.assertRaisesRegex(ValueError, "EQUIP criteria"):
            self._save_costume(account, generation, main, source["uid"], 2)

    def test_only_linked_unlocked_owned_companion_xp_contributes(self):
        account = self.store.register(
            "company-companion-" + uuid.uuid4().hex[:10], "local-password"
        )["id"]
        main = self._actor(account, "Sidekick Owner")
        generation = self.store.begin_session(account)
        self.store.select_character(account, generation, main["id"])
        character = self._owned_main(account, main)
        container = next(
            row["uid"] for row in character["inventory_containers"] if row["kind"] == 0
        )
        descriptor = next(
            row for row in companions.descriptors().values() if row["item_ref"] == 17878
        )
        source = grant(
            self.store,
            account,
            generation,
            main["id"],
            reference=17878,
            quantity=1,
            container=container,
            slot=0,
            allowed_references={17878},
        )
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO inventory_item_companions(uid,xp) VALUES(%s,%s)",
                (source["uid"], XP_BY_LEVEL[20]),
            )
        activation = struct.pack(">iq", descriptor["action_id"], source["uid"])
        result = companions.use(
            self.store, account, generation, main["id"], activation, in_fight=False
        )
        self.assertTrue(result["applied"])
        companion_id = result["companion"]["id"]
        with self.store.connection() as db:
            companion = db.execute(
                "SELECT linked,unlocked,xp FROM account_companions WHERE id=%s AND account_id=%s",
                (companion_id, account),
            ).fetchone()
            snapshot = load_company(db, self.store.character(account, main["id"], db))
        self.assertEqual(
            (companion["linked"], companion["unlocked"], companion["xp"]),
            (True, True, XP_BY_LEVEL[20]),
        )
        self.assertEqual(snapshot.score, 23)  # owner level 1 * 3 + companion level 20

        # An unrelated account's high-level character is not company progress.
        foreign = self.store.register(
            "company-foreign-" + uuid.uuid4().hex[:10], "local-password"
        )["id"]
        foreign_char = self._actor(foreign, "Foreign High")
        self._set_real_level(foreign_char["id"], 245)
        with self.store.connection() as db:
            own = load_company(db, self.store.character(account, main["id"], db))
        self.assertEqual(own.score, 23)

        # Public unlinking keeps the companion's native XP metadata on the
        # returned physical item but removes it from linked-company score.
        from wakfu_server.companion_equipment import unlink

        removed = unlink(
            self.store,
            account,
            generation,
            main["id"],
            struct.pack(">q", companion_id),
            in_fight=False,
        )
        self.assertTrue(removed["applied"])
        returned = next(
            row
            for row in removed["character"]["inventory_items"]
            if row.get("companion_xp") == XP_BY_LEVEL[20]
        )
        self.assertEqual(returned["reference"], 17878)
        reopened = self.reopen().character(account, main["id"])
        self.assertEqual(self._company(reopened).score, 3)

    def test_native_companion_equipment_uses_owned_company_rank_and_reconnects(self):
        from copy import deepcopy

        from wakfu_server import companion_equipment

        account = self.store.register(
            "company-gear-" + uuid.uuid4().hex[:10], "local-password"
        )["id"]
        main = self._actor(account, "Low Sidekick Owner")
        hero = self._actor(account, "Company Rank Hero")
        self._set_real_level(main["id"], 1)
        self._set_real_level(hero["id"], 60)
        generation = self.store.begin_session(account)
        self.store.select_character(account, generation, main["id"])
        heroes.add(self.store, account, generation, main["id"], hero["id"])
        owner = self._owned_main(account, main)
        self.assertEqual(self._company(owner).score, 183)
        self.assertEqual(self._company(owner).rank, 2)

        container = next(
            row["uid"] for row in owner["inventory_containers"] if row["kind"] == 0
        )
        descriptor = next(
            row for row in companions.descriptors().values() if row["item_ref"] == 17878
        )
        companion_item = grant(
            self.store,
            account,
            generation,
            main["id"],
            reference=17878,
            quantity=1,
            container=container,
            slot=0,
            allowed_references={17878},
        )
        result = companions.use(
            self.store,
            account,
            generation,
            main["id"],
            struct.pack(">iq", descriptor["action_id"], companion_item["uid"]),
            in_fight=False,
        )
        companion = result["companion"]
        gear = grant(
            self.store,
            account,
            generation,
            main["id"],
            reference=19545,
            quantity=1,
            container=container,
            slot=1,
            allowed_references={19545},
        )
        from wakfu_server.equipment import RULES

        self.assertIn(3, RULES[19545]["slots"])
        companion_equipment.save(
            self.store,
            account,
            generation,
            main["id"],
            struct.pack(">qhBbq", companion["id"], 1, 1, 3, gear["uid"]),
            in_fight=False,
        )
        after_save = self._owned_main(account, main)
        self.assertNotIn(
            gear["uid"], {row["uid"] for row in after_save["inventory_items"]}
        )

        companions.add_to_party(
            self.store,
            account,
            generation,
            main["id"],
            struct.pack(">q", companion["id"]),
        )
        reopened = self.reopen()
        reloaded_owner = reopened.character(account, main["id"])
        self.assertEqual(self._company(reloaded_owner).score, 184)
        self.assertEqual(reloaded_owner["level"], 1)
        with reopened.connection() as db:
            projected = companions.combat_sources(
                db, account, main["id"], owner_character=reloaded_owner, store=reopened
            )
        self.assertEqual(len(projected), 1)
        source = projected[0]
        self.assertEqual(source["companion_id"], companion["id"])
        self.assertEqual(
            source["equipment_entries"][0]["entry"]["item"]["uid"], gear["uid"]
        )
        # This native shoulder slot has no stat rows. The projection must keep
        # its real physical unit while leaving the NPC baseline untouched; it
        # must not borrow the low-level owner's build aptitudes or attributes.
        self.assertEqual(source["equipment_stat_bonuses"], {})
        from wakfu_server.combat_companions import native_stats

        expected_native = native_stats(
            companion["breed_ref"],
            source["level"],
            equipment_entries=source["equipment_entries"],
            owner=reloaded_owner,
        )
        compared_stats = ("hp", "max_hp", "ap", "mp", "wp", "initiative")
        self.assertEqual(
            {key: source[key] for key in compared_stats},
            {key: expected_native[key] for key in compared_stats},
        )

        foreign = self.store.register(
            "company-gear-foreign-" + uuid.uuid4().hex[:10], "local-password"
        )["id"]
        forged_owner = deepcopy(reloaded_owner)
        forged_owner["equipment_criterion_context"]["company_snapshot"][
            "account_id"
        ] = foreign
        with self.assertRaisesRegex(ValueError, "Foreign native company authority"):
            companion_equipment.criterion_context(forged_owner, source["level"])

        companion_equipment.retrieve_all(
            self.store,
            account,
            generation,
            main["id"],
            struct.pack(">q", companion["id"]),
            in_fight=False,
        )
        after_retrieve = self._owned_main(account, main)
        self.assertIn(
            gear["uid"], {row["uid"] for row in after_retrieve["inventory_items"]}
        )


if __name__ == "__main__":
    import unittest

    unittest.main()
