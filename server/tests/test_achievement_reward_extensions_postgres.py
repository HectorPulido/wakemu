"""Fixed XP and account emotes are durable, offline and replay safe."""
from postgres_case import PostgresCase
from wakfu_server.achievements import rewards, service, storage


class AchievementRewardExtensionPostgresTests(PostgresCase):
    def setUp(self):
        super().setUp()
        self.account = self.store.register("reward-extension-owner", "local-password")[
            "id"
        ]
        self.character = self.store.create_character(self.account, "Reward Extension")

    def test_fixed_xp_durable_level_health_and_receipt_replay(self):
        from wakfu_server.progression import XP_BY_LEVEL

        identity = self.character["id"]
        with self.store.connection() as db:
            before = self.store.character(self.account, identity, db)
            amount = XP_BY_LEVEL[5]
            storage.claim_reward(
                db, identity, 3800, "once", 1, dict(aeV=6, ckl=[amount])
            )
            packets = service.drain_rewards(db, self.store, before)
            self.assertEqual([opcode for opcode, _ in packets], [13613])
            current = self.store.character(self.account, identity, db)
            self.assertEqual(current["xp"], before["xp"] + amount)
            self.assertGreaterEqual(current["level"], 5)
            self.assertGreater(current["hp"], before["hp"])
            self.assertEqual(service.drain_rewards(db, self.store, before), [])
            self.assertFalse(
                storage.claim_reward(
                    db, identity, 3800, "once", 1, dict(aeV=6, ckl=[amount])
                )
            )
        self.assertEqual(
            self.reopen().character(self.account, identity)["xp"], before["xp"] + amount
        )

    def test_xp_overflow_rolls_back_entitlement_and_progress(self):
        identity = self.character["id"]
        with self.store.connection() as db:
            db.execute(
                "UPDATE character_progression SET xp=%s WHERE character_id=%s",
                ((1 << 63) - 1, identity),
            )
        with self.assertRaisesRegex(ValueError, "signed64"):
            with self.store.connection() as db:
                storage.claim_reward(
                    db, identity, 3800, "overflow", 1, dict(aeV=6, ckl=[1])
                )
                service.drain_rewards(db, self.store, self.character)
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT xp FROM character_progression WHERE character_id=%s",
                    (identity,),
                ).fetchone()["xp"],
                (1 << 63) - 1,
            )
            self.assertEqual(storage.pending_rewards(db, identity), [])

    def test_offline_emote_account_ownership_duplicate_and_reconnect(self):
        with self.store.connection() as db:
            service._owner(db, self.character)
            emote = db.execute(
                "SELECT emote_id FROM native_emote_definitions WHERE emote_id NOT IN (SELECT emote_id FROM account_emote_knowledge WHERE account_id=%s) ORDER BY emote_id LIMIT 1",
                (self.account,),
            ).fetchone()["emote_id"]
            first = rewards.grant(
                db, self.store, self.character, dict(aeV=3, ckl=[emote])
            )
            second = rewards.grant(
                db, self.store, self.character, dict(aeV=3, ckl=[emote])
            )
            self.assertIn(12266, [op for op, _ in first])
            self.assertNotIn(12266, [op for op, _ in second])
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM account_emote_knowledge WHERE account_id=%s AND emote_id=%s",
                    (self.account, emote),
                ).fetchone()["n"],
                1,
            )
            with self.assertRaises(ValueError):
                service._owner(db, dict(self.character, account_id=self.account + 9999))
        with self.reopen().connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM account_emote_knowledge WHERE account_id=%s AND emote_id=%s",
                    (self.account, emote),
                ).fetchone()["n"],
                1,
            )
