from types import SimpleNamespace
from psycopg.types.json import Jsonb

from postgres_case import PostgresCase
from wakfu_server.monsters import owned_instance
from wakfu_server import monster_corpses as corpses


class DurableMonsterCorpsesTests(PostgresCase):
    def setUp(self):
        super().setUp()
        self.member = owned_instance(
            5525, 1, -201, map_id=1134, instance_id=7, x=-7, y=-7, z=-1
        )
        with self.store.connection() as db:
            identity = db.execute(
                "INSERT INTO combat_fights(status) VALUES('finished') RETURNING id"
            ).fetchone()["id"]
        self.fight = SimpleNamespace(
            id=identity,
            phase="finished",
            actors={-201: SimpleNamespace(hp=0, controlled=False)},
        )

    def retain(self, store=None):
        with (store or self.store).connection() as db:
            return corpses.retain(db, self.fight, (self.member,))

    def row(self, store=None):
        with (store or self.store).connection() as db:
            return db.execute("SELECT * FROM monster_corpses").fetchone()

    def test_default_hour_survives_store_reopen_and_idempotent_settlement(self):
        self.retain()
        original = self.row()
        self.assertEqual(
            (original["expires_at"] - original["created_at"]).total_seconds(), 3600
        )
        self.assertEqual(original["lifetime_seconds"], 3600)
        reopened = self.reopen()
        self.retain(reopened)
        self.assertEqual(original, self.row(reopened))
        self.assertNotEqual(original["actor_id"], self.member["id"])
        self.assertEqual(original["monster"]["x"], self.member["x"])
        with reopened.connection() as db:
            self.assertEqual(len(corpses.snapshots(db, 1134, 7)), 1)

    def test_failed_settlement_rolls_back_corpse_with_caller(self):
        with self.assertRaisesRegex(RuntimeError, "rollback"):
            with self.store.connection() as db:
                corpses.retain(db, self.fight, (self.member,))
                self.assertEqual(
                    db.execute("SELECT count(*) AS n FROM monster_corpses").fetchone()[
                        "n"
                    ],
                    1,
                )
                raise RuntimeError("rollback")
        self.assertIsNone(self.row())

    def test_policy_change_applies_to_new_corpses_without_altering_existing(self):
        self.retain()
        original = self.row()
        with self.store.connection() as db:
            db.execute(
                "UPDATE settings SET value=%s WHERE name='monster_corpse_policy'",
                (Jsonb({"lifetime_seconds": 600}),),
            )
            new_id = db.execute(
                "INSERT INTO combat_fights(status) VALUES('finished') RETURNING id"
            ).fetchone()["id"]
        self.retain()
        self.assertEqual(original, self.row())
        self.fight.id = new_id
        self.retain()
        with self.store.connection() as db:
            new = db.execute(
                "SELECT * FROM monster_corpses WHERE fight_id=%s", (new_id,)
            ).fetchone()
        self.assertEqual(new["lifetime_seconds"], 600)
        self.assertEqual((new["expires_at"] - new["created_at"]).total_seconds(), 600)

    def test_invalid_policy_rolls_back_entire_callers_transaction(self):
        for invalid in (0, -1, True, 1.5, "600", 2678401):
            with self.subTest(invalid=invalid):
                with self.assertRaisesRegex(ValueError, "lifetime policy"):
                    with self.store.connection() as db:
                        db.execute(
                            "UPDATE settings SET value=%s WHERE name='monster_corpse_policy'",
                            (Jsonb({"lifetime_seconds": invalid}),),
                        )
                        corpses.retain(db, self.fight, (self.member,))
                self.assertIsNone(self.row())
                with self.store.connection() as db:
                    policy = db.execute(
                        "SELECT value FROM settings WHERE name='monster_corpse_policy'"
                    ).fetchone()["value"]
                self.assertEqual(policy, {"lifetime_seconds": 3600})

    def test_visibility_is_isolated_by_map_and_instance(self):
        self.retain()
        with self.store.connection() as db:
            self.assertEqual(len(corpses.snapshots(db, 1134, 7)), 1)
            self.assertEqual(corpses.snapshots(db, 1134, 0), ())
            self.assertEqual(corpses.snapshots(db, 1135, 7), ())

    def test_expiry_claim_rolls_back_and_then_publishes_once_without_reviving(self):
        self.retain()
        with self.store.connection() as db:
            # Shift both endpoints together; the one-hour constraint remains.
            db.execute(
                "UPDATE monster_corpses SET created_at=created_at-INTERVAL '2 hours', "
                "expires_at=expires_at-INTERVAL '2 hours'"
            )
        expired = self.row()
        with self.assertRaisesRegex(RuntimeError, "delivery failed"):
            with self.store.connection() as db:
                self.assertEqual(set(corpses.expire(db)), {(1134, 7)})
                raise RuntimeError("delivery failed")
        self.assertFalse(self.row()["expiry_published"])
        with self.store.connection() as db:
            self.assertEqual(corpses.snapshots(db, 1134, 7), ())
            removals = corpses.expire(db)
            self.assertEqual(set(removals), {(1134, 7)})
            self.assertEqual(removals[(1134, 7)][0][0], 12304)
        with self.reopen().connection() as db:
            self.assertEqual(corpses.expire(db), {})
            self.assertEqual(corpses.snapshots(db, 1134, 7), ())
        self.retain()
        row = self.row()
        self.assertEqual(row["actor_id"], expired["actor_id"])
        self.assertEqual(row["expires_at"], expired["expires_at"])
        self.assertTrue(row["expiry_published"])
