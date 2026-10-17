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
            from wakfu_server.combat_drop_delivery import _container_can_hold
            from wakfu_server.inventory_move import ACQUISITION_STACKS

            containers = [
                dict(row)
                for row in db.execute(
                    "SELECT * FROM inventory_containers WHERE character_id=%s ORDER BY kind,uid",
                    (identity,),
                ).fetchall()
            ]
            self.assertEqual(
                [
                    (row["reference"], row["capacity"])
                    for row in containers
                    if row["kind"] == 0
                ],
                [(2175, 30)],
            )
            eligible = [row for row in containers if _container_can_hold(row, identity)]
            # Fill actual native slots through the normal reward producer.
            # Full stacks cannot merge, and extra eligible bags must also be
            # full before this case can establish a capacity retry.
            maximum = min(ACQUISITION_STACKS[2021]["maximum"], 32767)
            slots = sum(row["capacity"] for row in eligible)
            rewards.grant(
                db, self.store, character, dict(aeV=5, ckl=[2021, slots * maximum])
            )
            blockers = self.store.character(account, identity, db)["inventory_items"]
            self.assertEqual(len(blockers), slots)
            self.assertEqual(
                {(row["reference"], row["quantity"]) for row in blockers},
                {(2021, maximum)},
            )
            self.assertEqual(
                {(row["container"], row["slot"]) for row in blockers},
                {
                    (bag["uid"], slot)
                    for bag in eligible
                    for slot in range(bag["capacity"])
                },
            )
            occupied = blockers[0]["uid"]
            remaining_blockers = {
                row["uid"]: (
                    row["reference"],
                    row["quantity"],
                    row["container"],
                    row["slot"],
                )
                for row in blockers
                if row["uid"] != occupied
            }
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
            [
                (r["reference"], r["quantity"])
                for r in selected["inventory_items"]
                if r["uid"] not in remaining_blockers
            ],
            [(7361, 5)],
        )
        self.assertEqual(
            {
                row["uid"]: (
                    row["reference"],
                    row["quantity"],
                    row["container"],
                    row["slot"],
                )
                for row in selected["inventory_items"]
                if row["uid"] in remaining_blockers
            },
            remaining_blockers,
        )
        self.assertNotIn(occupied, {row["uid"] for row in selected["inventory_items"]})
        self.assertEqual(selected["inventory_containers"], containers)
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
