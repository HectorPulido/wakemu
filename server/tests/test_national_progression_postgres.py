"""Owned durable component authority, not invented crime or merit rewards."""
from dataclasses import replace
import struct

from postgres_case import PostgresCase
import test_equipment_level_groups_postgres as gear_fixture
from wakfu_server import nation_state, national_progression as national
from wakfu_server.equipment_conditions import evaluate


class NationalProgressionPostgresTests(PostgresCase):
    _owner = gear_fixture.EquipmentLevelGroupsPostgresTests._owner
    _grant = gear_fixture.EquipmentLevelGroupsPostgresTests._grant
    _save = gear_fixture.EquipmentLevelGroupsPostgresTests._save

    def imported(self, account, owner, *, score=-70, rank=7):
        with self.store.connection() as db:
            ranks = national._ranks(db, national.VERSION)
        return national.NationalSnapshot(
            owner["id"],
            account,
            30,
            rank,
            ((30, score), (31, -70)),
            ranks,
            national.VERSION,
            "native_import",
        )

    def restore(self, account, generation, owner, snapshot, key):
        with self.store.connection() as db:
            self.store.lock_character(db, account, generation, owner["id"])
            return national.restore_import(
                db, account, owner["id"], snapshot.record(), receipt_key=key
            )

    def test_real_constructor_enrollment_and_unknown_legacy_do_not_create_fake_authority(
        self,
    ):
        account, generation, owner = self._owner(100)
        context = owner["equipment_criterion_context"]
        snapshot = national.NationalSnapshot.from_record(
            context["national_progression"]
        )
        self.assertEqual(
            (snapshot.provenance, snapshot.rank_id, snapshot.crime_scores),
            ("native_constructor", 0, ()),
        )
        self.assertEqual(nation_state.synchro(owner), bytes(27))
        self.assertEqual(national.citizen_section(owner), bytes(4))
        before = owner["equipment_criterion_context"]["completed_achievements"]
        chosen = nation_state.enroll(
            self.store,
            account,
            generation,
            owner["id"],
            struct.pack(">i", 30) + bytes(2),
        )
        known = national.NationalSnapshot.from_record(
            chosen["equipment_criterion_context"]["national_progression"]
        )
        self.assertEqual(known.nation_id, 30)
        self.assertEqual(
            chosen["equipment_criterion_context"]["completed_achievements"], before
        )
        with self.store.connection() as db:
            # Model a real pre276 character; migration276 contains no backfill.
            db.execute(
                "DELETE FROM character_national_authority WHERE character_id=%s",
                (owner["id"],),
            )
        for _ in range(2):
            old = self.store.character(account, owner["id"])
            self.assertNotIn("national_progression", old["equipment_criterion_context"])
            with self.assertRaises(ValueError):
                evaluate(
                    "GetCrimeScore() <= -70",
                    item={},
                    selected=(),
                    owned={},
                    criterion_context=old["equipment_criterion_context"],
                )
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM character_national_authority"
                ).fetchone()["n"],
                0,
            )

    def test_owned_import_real_equipment_reconnect_wire_and_replay_preserve_signed_scores(
        self,
    ):
        account, generation, owner = self._owner(245)
        owner = nation_state.enroll(
            self.store,
            account,
            generation,
            owner["id"],
            struct.pack(">i", 30) + bytes(2),
        )
        negative = self.imported(account, owner)
        self.assertTrue(
            self.restore(account, generation, owner, negative, "original-source-a")
        )
        loaded = self.store.character(account, owner["id"])
        item = self._grant(account, generation, loaded, 10040, 0)
        equipped = self._save(account, generation, loaded, item)
        self.assertTrue(
            any(row["uid"] == item["uid"] for row in equipped["inventory_items"])
        )
        cleared = self._save(account, generation, equipped)
        positive = self.imported(account, cleared, score=500)
        self.assertTrue(
            self.restore(account, generation, cleared, positive, "original-source-b")
        )
        self.assertFalse(
            self.restore(account, generation, cleared, negative, "original-source-a")
        )
        loaded = self.reopen().character(account, owner["id"])
        context = loaded["equipment_criterion_context"]
        self.assertTrue(
            evaluate(
                "GetCrimeScore() >= 500 and HasPvpRank(7)",
                item={},
                selected=(),
                owned={},
                criterion_context=context,
            )
        )
        self.assertEqual(nation_state.synchro(loaded), bytes(26) + b"\x07")
        self.assertEqual(
            national.citizen_section(loaded),
            struct.pack(">HiiiiH", 2, 30, 500, 31, -70, 0),
        )
        other = self._grant(account, generation, loaded, 9728, 1)
        saved = self._save(account, generation, loaded, other)
        self.assertEqual(
            saved["equipment_criterion_context"]["national_progression"]["rank_id"], 7
        )
        cleared = self._save(account, generation, saved)
        ranked = self._grant(account, generation, cleared, 18932, 2)
        ranked_build = self._save(account, generation, cleared, ranked)
        self.assertEqual(
            ranked_build["equipment_criterion_context"]["national_progression"][
                "rank_id"
            ],
            7,
        )
        with self.assertRaisesRegex(ValueError, "source changed on replay"):
            self.restore(account, generation, cleared, positive, "original-source-a")
        with self.assertRaisesRegex(ValueError, "owner or nation mismatch"):
            self.restore(
                account,
                generation,
                cleared,
                replace(positive, account_id=account + 100, source_sha256=""),
                "foreign",
            )

    def test_native_rank_source_is_immutable_and_constructor_cannot_reset_an_import(
        self,
    ):
        account, generation, owner = self._owner(100)
        owner = nation_state.enroll(
            self.store,
            account,
            generation,
            owner["id"],
            struct.pack(">i", 30) + bytes(2),
        )
        self.restore(
            account, generation, owner, self.imported(account, owner), "original"
        )
        with self.store.connection() as db:
            national.initialize(db, account, owner["id"])
        self.assertEqual(
            self.store.character(account, owner["id"])["equipment_criterion_context"][
                "national_progression"
            ]["rank_id"],
            7,
        )
        for statement in (
            "UPDATE native_national_pvp_ranks SET merit_threshold=1",
            "DELETE FROM native_national_progression_versions",
        ):
            with self.subTest(statement=statement), self.assertRaisesRegex(
                Exception, "append-only"
            ):
                with self.store.connection() as db:
                    db.execute(statement)

    def test_actual_companion_refuses_negative_crime_gear_even_when_its_owner_qualifies(
        self,
    ):
        from wakfu_server import companions, companion_equipment
        from wakfu_server.character_levels import XP_BY_LEVEL

        account, generation, owner = self._owner(245)
        owner = nation_state.enroll(
            self.store,
            account,
            generation,
            owner["id"],
            struct.pack(">i", 30) + bytes(2),
        )
        self.restore(
            account,
            generation,
            owner,
            self.imported(account, owner),
            "original-negative-owner",
        )
        descriptor = next(
            row for row in companions.descriptors().values() if row["item_ref"] == 17878
        )
        activation = self._grant(account, generation, owner, 17878, 0)
        companion = companions.use(
            self.store,
            account,
            generation,
            owner["id"],
            struct.pack(">iq", descriptor["action_id"], activation["uid"]),
            in_fight=False,
        )["companion"]
        with self.store.connection() as db:
            db.execute(
                "UPDATE account_companions SET xp=%s WHERE id=%s",
                (XP_BY_LEVEL[100], companion["id"]),
            )
        item = self._grant(account, generation, owner, 10040, 1)
        body = struct.pack(">qhBbq", companion["id"], 1, 1, 4, item["uid"])
        with self.assertRaisesRegex(ValueError, "EQUIP"):
            companion_equipment.save(
                self.store, account, generation, owner["id"], body, in_fight=False
            )
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM companion_equipment WHERE companion_id=%s",
                    (companion["id"],),
                ).fetchone()["n"],
                0,
            )
            self.assertEqual(
                db.execute(
                    "SELECT quantity FROM inventory_items WHERE uid=%s AND character_id=%s",
                    (item["uid"], owner["id"]),
                ).fetchone()["quantity"],
                1,
            )
