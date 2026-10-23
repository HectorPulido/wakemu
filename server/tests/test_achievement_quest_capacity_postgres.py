"""Real personal/account QUEST limits preserve earned journal entitlements."""
from postgres_case import PostgresCase
from wakfu_server.achievements import rewards, service, storage
from wakfu_server.items import quest_inventory, account_quest_inventory


class AchievementQuestCapacityPostgresTests(PostgresCase):
    def test_native_quest_caps_preserve_pending_rewards_and_retry_once(self):
        account = self.store.register("journal-quest-capacity", "local-password")["id"]
        character = self.store.create_character(account, "Quest Capacity")
        identity = character["id"]
        generation = self.store.begin_session(account)
        self.store.select_character(account, generation, identity)
        personal, shared = 21001, 21599
        self.assertIn(personal, quest_inventory.REFERENCES)
        self.assertEqual(quest_inventory.MAXIMUMS[personal], 9999)
        self.assertIn(shared, account_quest_inventory.REFERENCES)
        period = "hunter-daily:qualification"
        with self.store.connection() as db:
            # Use the real native quantity writers, not injected capacity errors.
            quest_inventory.grant(db, identity, personal, 9999)
            account_quest_inventory.grant(db, account, shared, 32767)
            for ordinal, reference in enumerate((personal, shared), 1):
                payload = dict(d=ordinal, aeV=5, ckl=[reference, 1])
                self.assertTrue(
                    storage.enqueue_reward(
                        db, identity, 3766, period, str(ordinal), payload
                    )
                )
            self.assertEqual(service.drain_rewards(db, self.store, character), [])
            self.assertEqual(len(storage.pending_rewards(db, identity)), 2)
            self.assertEqual(
                quest_inventory.quantity(
                    self.store.character(account, identity, db), [personal]
                ),
                9999,
            )
            self.assertEqual(
                account_quest_inventory.payment(db, account, shared, 1)["quantity"],
                32767,
            )
            # Invalid requests remain validation failures, not retryable capacity.
            for grant, args in (
                (quest_inventory.grant, (identity, personal, 0)),
                (quest_inventory.grant, (identity, -1, 1)),
                (account_quest_inventory.grant, (0, shared, 1)),
                (account_quest_inventory.grant, (account, -1, 1)),
            ):
                with self.assertRaises(ValueError) as caught:
                    grant(db, *args)
                self.assertNotIsInstance(
                    caught.exception, quest_inventory.QuestCapacity
                )
        # Selection itself retries the real outbox but leaves full rewards earned.
        generation = self.store.begin_session(account)
        self.store.select_character(account, generation, identity)
        with self.store.connection() as db:
            self.assertEqual(len(storage.pending_rewards(db, identity)), 2)
            from wakfu_server.dungeon_entry_payment import consume

            consume(db, [identity], personal, 1)
            account_quest_inventory.consume(db, account, shared, 1)
            # A surrounding settlement rollback also reverts grants and delivered flags.
            with self.assertRaisesRegex(RuntimeError, "settlement rollback"):
                with db.transaction():
                    self.assertTrue(service.drain_rewards(db, self.store, character))
                    self.assertEqual(storage.pending_rewards(db, identity), [])
                    raise RuntimeError("settlement rollback")
            self.assertEqual(len(storage.pending_rewards(db, identity)), 2)
            self.assertEqual(
                quest_inventory.quantity(
                    self.store.character(account, identity, db), [personal]
                ),
                9998,
            )
            self.assertEqual(
                account_quest_inventory.payment(db, account, shared, 1)["quantity"],
                32766,
            )
            self.assertTrue(service.drain_rewards(db, self.store, character))
            self.assertEqual(storage.pending_rewards(db, identity), [])
            self.assertEqual(service.drain_rewards(db, self.store, character), [])
        # Reconnect cannot award again after both real capacity slots were filled.
        generation = self.store.begin_session(account)
        self.store.select_character(account, generation, identity)
        with self.store.connection() as db:
            self.assertEqual(storage.pending_rewards(db, identity), [])
            self.assertEqual(
                quest_inventory.quantity(
                    self.store.character(account, identity, db), [personal]
                ),
                9999,
            )
            self.assertEqual(
                account_quest_inventory.payment(db, account, shared, 1)["quantity"],
                32767,
            )
            for ordinal, reference in enumerate((personal, shared), 1):
                self.assertFalse(
                    storage.enqueue_reward(
                        db,
                        identity,
                        3766,
                        period,
                        str(ordinal),
                        dict(d=ordinal, aeV=5, ckl=[reference, 1]),
                    )
                )
