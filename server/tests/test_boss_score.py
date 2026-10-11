"""Durable local boss score accounting, exclusion, replay and rollback."""
from postgres_case import PostgresCase
from wakfu_server.maps import boss_score


class BossScorePostgresTests(PostgresCase):
    def setUp(self):
        super().setUp()
        account = self.store.register("boss-score", "local-password")["id"]
        self.cid = self.store.create_character(account, "ScoreWinner")["id"]
        with self.store.connection() as db:
            self.fight = db.execute(
                "INSERT INTO combat_fights(status) VALUES('active') RETURNING id"
            ).fetchone()["id"]
            db.execute(
                "INSERT INTO combat_fight_participants(fight_id,character_id,account_id,team) VALUES(%s,%s,%s,0)",
                (self.fight, self.cid, account),
            )
            self.profile = boss_score.freeze(
                db,
                self.fight,
                monsters={-1: {"ref": 4378, "team": 1}, -2: {"ref": 1, "team": 1}},
                player_ids=[self.cid],
            )

    def finish(self, db, **options):
        db.execute(
            "UPDATE combat_fights SET status='finished' WHERE id=%s", (self.fight,)
        )
        return boss_score.finalize(db, self.fight, **options)

    def record(self, db, event="hit", **changes):
        options = dict(
            event_id=event,
            source_id=self.cid,
            target_id=-1,
            owner_actor_id=self.cid,
            post_mitigation_damage=100,
            armor_absorbed=50,
            round_number=1,
        )
        options.update(changes)
        return boss_score.record_damage(db, self.fight, **options)

    def test_damage_armor_owned_summons_exclusions_and_event_replay(self):
        with self.store.connection() as db:
            self.assertTrue(self.record(db))
            self.assertTrue(self.record(db))
            self.assertTrue(
                self.record(
                    db, "summon", source_id=-10, source_is_registered_summon=True
                )
            )
            self.assertFalse(self.record(db, "late-round", round_number=21))
            self.assertFalse(self.record(db, "add", target_id=-2))
            self.assertFalse(self.record(db, "foreign", owner_actor_id=self.cid + 999))
            self.assertFalse(self.record(db, "unregistered", source_id=-11))
            result = self.finish(db, completed_rounds=20, survived=True, winning_team=0)
            self.assertEqual(result["score"], 300)
            self.assertTrue(result["eligible"])
            self.assertEqual(boss_score.drop_context(db, self.fight), {"score": 300})
        with self.store.connection() as db:
            self.assertEqual(
                self.finish(db, completed_rounds=20, survived=True, winning_team=0),
                result,
            )
            # Replayed terminal checkpoint events are immutable, not new damage.
            self.assertTrue(self.record(db))
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM boss_score_damage_receipts WHERE fight_id=%s",
                    (self.fight,),
                ).fetchone()["n"],
                2,
            )
            with self.assertRaisesRegex(ValueError, "finalized"):
                self.record(db, "late")

    def test_rollback_and_conflicting_delivery_never_inflate_score(self):
        with self.assertRaisesRegex(
            RuntimeError, "abort"
        ), self.store.connection() as db:
            self.record(db)
            raise RuntimeError("abort")
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM boss_score_damage_receipts WHERE fight_id=%s",
                    (self.fight,),
                ).fetchone()["n"],
                0,
            )
            self.record(db)
        with self.assertRaisesRegex(
            ValueError, "replay changed"
        ), self.store.connection() as db:
            self.record(db, post_mitigation_damage=101)
        with self.store.connection() as db:
            result = self.finish(db, completed_rounds=19, survived=True, winning_team=0)
            self.assertEqual(result["score"], 0)
            self.assertFalse(result["eligible"])
            self.assertEqual(boss_score.drop_context(db, self.fight), {})

    def test_profile_freezes_and_unconfigured_boss_is_not_inferred(self):
        from psycopg.types.json import Jsonb

        with self.store.connection() as db:
            db.execute(
                "UPDATE settings SET value=%s WHERE name='boss_score_policy'",
                (Jsonb(dict(schema_version=1, policy=boss_score.POLICY, profiles={})),),
            )
            self.record(db)
            self.assertEqual(
                self.finish(db, completed_rounds=20, survived=True, winning_team=0)[
                    "score"
                ],
                150,
            )
            other = db.execute(
                "INSERT INTO combat_fights(status) VALUES('active') RETURNING id"
            ).fetchone()["id"]
            self.assertIsNone(
                boss_score.freeze(
                    db,
                    other,
                    monsters={-3: {"ref": 5608, "team": 1}},
                    player_ids=[self.cid],
                )
            )
