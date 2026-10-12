"""Selection retries earned rewards before its final absolute snapshot."""
import struct
from postgres_case import PostgresCase
from wakfu_server.achievements import rewards, service, storage


class AchievementSelectionRetryPostgresTests(PostgresCase):
    def test_full_bag_retry_selection_reloads_all_state_once_after_session_fence(self):
        from wakfu_server import inventory_actions, emotes
        from wakfu_server.progression import XP_BY_LEVEL

        account = self.store.register("selection-retry-owner", "local-password")["id"]
        character = self.store.create_character(account, "Selection Retry")
        identity = character["id"]
        generation = self.store.begin_session(account)
        self.store.select_character(account, generation, identity)
        with self.store.connection() as db:
            db.execute(
                "UPDATE inventory_containers SET capacity=1 WHERE character_id=%s AND kind=0",
                (identity,),
            )
            rewards.grant(db, self.store, character, dict(aeV=5, ckl=[2021, 1]))
            occupied = self.store.character(account, identity, db)["inventory_items"][
                0
            ]["uid"]
            emote = db.execute(
                "SELECT emote_id FROM native_emote_definitions WHERE emote_id NOT IN (SELECT emote_id FROM account_emote_knowledge WHERE account_id=%s) ORDER BY emote_id LIMIT 1",
                (account,),
            ).fetchone()["emote_id"]
            storage.claim_reward(
                db, identity, 238, "once", 1, dict(aeV=5, ckl=[7361, 5])
            )
            self.assertEqual(service.drain_rewards(db, self.store, character), [])
            # XP and emote are earned while offline; selection must publish their final state.
            storage.claim_reward(
                db, identity, 3800, "once", 2, dict(aeV=6, ckl=[XP_BY_LEVEL[5]])
            )
            storage.claim_reward(
                db, identity, 5164, "once", 3, dict(aeV=3, ckl=[emote])
            )
        inventory_actions.destroy(
            self.store, account, generation, identity, struct.pack(">q", occupied)
        )
        newer = self.store.begin_session(account)
        foreign = self.store.register("selection-retry-foreign", "local-password")["id"]
        foreign_generation = self.store.begin_session(foreign)
        for owner, lease in ((account, generation), (foreign, foreign_generation)):
            with self.assertRaises(ValueError):
                self.store.select_character(owner, lease, identity)
        with self.store.connection() as db:
            self.assertEqual(len(storage.pending_rewards(db, identity)), 3)
            self.assertEqual(
                self.store.character(account, identity, db)["xp"], character["xp"]
            )
        selected = self.store.select_character(account, newer, identity)
        self.assertEqual(
            [(r["reference"], r["quantity"]) for r in selected["inventory_items"]],
            [(7361, 5)],
        )
        self.assertEqual(selected["xp"], character["xp"] + XP_BY_LEVEL[5])
        self.assertGreaterEqual(selected["level"], 5)
        self.assertGreater(selected["hp"], character["hp"])
        again = self.store.select_character(account, newer, identity)
        self.assertEqual(again["xp"], selected["xp"])
        self.assertEqual(
            [r["uid"] for r in again["inventory_items"]],
            [r["uid"] for r in selected["inventory_items"]],
        )
        with self.store.connection() as db:
            self.assertEqual(storage.pending_rewards(db, identity), [])
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM account_emote_knowledge WHERE account_id=%s AND emote_id=%s",
                    (account, emote),
                ).fetchone()["n"],
                1,
            )
            self.assertEqual(
                emotes.packet(self.store, account), emotes.snapshot(db, account)
            )
