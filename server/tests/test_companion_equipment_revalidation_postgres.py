"""Persisted companion gear keeps custody while NPC eligibility changes."""
import struct
import unittest
import uuid

from postgres_case import PostgresCase
from wakfu_server import character_levels
from wakfu_server.characters import companion_equipment, companions
from wakfu_server.inventory_items import grant


class CompanionEquipmentRevalidationPostgresTests(PostgresCase):
    def setUp(self):
        super().setUp()
        self.account = self.store.register(
            "companion-revalidate-" + uuid.uuid4().hex[:10], "local-password"
        )["id"]
        self.character = self.store.create_character(self.account, "Revalidation Owner")
        self.generation = self.store.begin_session(self.account)
        self.store.select_character(self.account, self.generation, self.character["id"])
        self.container = next(
            row["uid"]
            for row in self.character["inventory_containers"]
            if row["kind"] == 0
        )
        descriptor = next(
            row for row in companions.descriptors().values() if row["item_ref"] == 17878
        )
        sidekick = grant(
            self.store,
            self.account,
            self.generation,
            self.character["id"],
            reference=descriptor["item_ref"],
            quantity=1,
            container=self.container,
            slot=0,
            allowed_references={descriptor["item_ref"]},
        )
        self.companion = companions.use(
            self.store,
            self.account,
            self.generation,
            self.character["id"],
            struct.pack(">iq", descriptor["action_id"], sidekick["uid"]),
            in_fight=False,
        )["companion"]

    def _grant(self, reference, slot=1):
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

    def _equip(self, item, slot):
        return companion_equipment.save(
            self.store,
            self.account,
            self.generation,
            self.character["id"],
            struct.pack(">qhBbq", self.companion["id"], 1, 1, slot, item["uid"]),
            in_fight=False,
        )

    def _project(self):
        with self.store.connection() as db:
            rows = companions.combat_sources(
                db, self.account, self.character["id"], store=self.store
            )
        self.assertEqual(1, len(rows))
        return rows[0]

    def test_real_level_criterion_rechecks_effects_without_dropping_custody(self):
        from wakfu_server.equipment import RULES

        # Native 14891 is account-bound and has GetRealLevel() <= 30. Its XP
        # stays above 30 so the account's loaded cap alone drives 30→31→30.
        with self.store.connection() as db:
            db.execute(
                "UPDATE characters SET level=30 WHERE id=%s", (self.character["id"],)
            )
            db.execute(
                "UPDATE account_companions SET xp=%s WHERE id=%s",
                (character_levels.XP_BY_LEVEL[31], self.companion["id"]),
            )
        item = self._grant(14891)
        slot = RULES[14891]["slots"][0]
        self._equip(item, slot)
        companions.add_to_party(
            self.store,
            self.account,
            self.generation,
            self.character["id"],
            struct.pack(">q", self.companion["id"]),
        )

        at_30 = self._project()
        self.assertEqual(
            item["uid"], at_30["equipment_entries"][0]["entry"]["item"]["uid"]
        )
        from wakfu_server.companion_equipment import stat_bonuses

        entries = at_30["equipment_entries"]
        at_30_effects = stat_bonuses(entries, self.character, 30)
        self.assertEqual([item["uid"]], at_30_effects["equipped_uids"])

        with self.store.connection() as db:
            db.execute(
                "UPDATE characters SET level=31 WHERE id=%s", (self.character["id"],)
            )
        at_31 = self._project()
        self.assertEqual(
            item["uid"], at_31["equipment_entries"][0]["entry"]["item"]["uid"]
        )
        self.assertEqual({}, dict(at_31["equipment_stat_bonuses"]))
        at_31_effects = stat_bonuses(at_31["equipment_entries"], self.character, 31)
        self.assertEqual([], at_31_effects["equipped_uids"])

        with self.store.connection() as db:
            db.execute(
                "UPDATE characters SET level=30 WHERE id=%s", (self.character["id"],)
            )
        restored = self._project()
        self.assertEqual(
            item["uid"], restored["equipment_entries"][0]["entry"]["item"]["uid"]
        )
        restored_effects = stat_bonuses(
            restored["equipment_entries"], self.character, 30
        )
        self.assertEqual([item["uid"]], restored_effects["equipped_uids"])

        companions.remove_from_party(
            self.store,
            self.account,
            self.generation,
            self.character["id"],
            self.companion["id"],
        )
        companion_equipment.retrieve_all(
            self.store,
            self.account,
            self.generation,
            self.character["id"],
            struct.pack(">q", self.companion["id"]),
            in_fight=False,
        )
        with self.store.connection() as db:
            row = db.execute(
                "SELECT uid,quantity FROM inventory_items WHERE uid=%s AND character_id=%s",
                (item["uid"], self.character["id"]),
            ).fetchone()
        self.assertEqual((item["uid"], 1), (row["uid"], row["quantity"]))

    def test_native_minimum_level_rechecks_effects_after_cap_reduction(self):
        from wakfu_server.character_levels import XP_BY_LEVEL
        from wakfu_server.element_selection import select as select_elements
        from wakfu_server.equipment import RULES
        from wakfu_server.companion_equipment import stat_bonuses

        ring_masks = (
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
        candidate = next(
            (
                (reference, mask)
                for reference, mask in ring_masks
                if RULES[reference]["minimum_level"] > 30
            ),
            None,
        )
        self.assertIsNotNone(
            candidate, "expected an admitted native ring above level 30"
        )
        reference, mask = candidate
        level = 245
        with self.store.connection() as db:
            db.execute(
                "UPDATE characters SET level=%s WHERE id=%s",
                (level, self.character["id"]),
            )
            db.execute(
                "UPDATE account_companions SET xp=%s WHERE id=%s",
                (XP_BY_LEVEL[level], self.companion["id"]),
            )
        item = self._grant(reference)
        select_elements(
            self.store,
            self.account,
            self.generation,
            self.character["id"],
            struct.pack(">qBB", item["uid"], mask, 0),
        )
        self._equip(item, RULES[reference]["slots"][0])
        companions.add_to_party(
            self.store,
            self.account,
            self.generation,
            self.character["id"],
            struct.pack(">q", self.companion["id"]),
        )

        at_245 = self._project()
        entries = at_245["equipment_entries"]
        self.assertEqual(item["uid"], entries[0]["entry"]["item"]["uid"])
        self.assertEqual(
            [item["uid"]], stat_bonuses(entries, self.character, level)["equipped_uids"]
        )

        with self.store.connection() as db:
            db.execute(
                "UPDATE characters SET level=30 WHERE id=%s", (self.character["id"],)
            )
        at_30 = self._project()
        self.assertEqual(
            item["uid"], at_30["equipment_entries"][0]["entry"]["item"]["uid"]
        )
        self.assertEqual(
            [],
            stat_bonuses(at_30["equipment_entries"], self.character, 30)[
                "equipped_uids"
            ],
        )

        with self.store.connection() as db:
            db.execute(
                "UPDATE characters SET level=%s WHERE id=%s",
                (level, self.character["id"]),
            )
        restored = self._project()
        self.assertEqual(
            [item["uid"]],
            stat_bonuses(restored["equipment_entries"], self.character, level)[
                "equipped_uids"
            ],
        )

        companions.remove_from_party(
            self.store,
            self.account,
            self.generation,
            self.character["id"],
            self.companion["id"],
        )
        companion_equipment.retrieve_all(
            self.store,
            self.account,
            self.generation,
            self.character["id"],
            struct.pack(">q", self.companion["id"]),
            in_fight=False,
        )
        with self.store.connection() as db:
            row = db.execute(
                "SELECT uid,quantity FROM inventory_items WHERE uid=%s AND character_id=%s",
                (item["uid"], self.character["id"]),
            ).fetchone()
        self.assertEqual((item["uid"], 1), (row["uid"], row["quantity"]))


def load_tests(loader, tests, pattern):
    suite = unittest.TestSuite()
    suite.addTests(
        loader.loadTestsFromTestCase(CompanionEquipmentRevalidationPostgresTests)
    )
    return suite
