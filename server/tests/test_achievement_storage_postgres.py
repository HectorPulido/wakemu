"""Achievement state, event and reward receipts share the owned transaction."""
import unittest
from postgres_case import PostgresCase
from wakfu_server.achievements import storage, rewards, service


class AchievementStoragePostgresTests(PostgresCase):
    def setUp(self):
        super().setUp()
        self.account = self.store.register("achievement-owner", "local-password")["id"]
        self.character = self.store.create_character(self.account, "Achievement Owner")

    def test_progress_authority_roundtrip_event_dedupe_conflict_and_rollback(self):
        with self.store.connection() as db:
            initial = storage.load_locked(db, self.character["id"])
            state = dict(
                initial,
                variables={"51": 3},
                objectives=[617],
                running=[239],
                completed=[238],
                completion_dates={"238": 1000},
            )
            storage.store(db, self.character["id"], state)
            self.assertTrue(
                storage.record_event(
                    db, self.character["id"], "fight:7", {"breeds": [39]}
                )
            )
            self.assertFalse(
                storage.record_event(
                    db, self.character["id"], "fight:7", {"breeds": [39]}
                )
            )
            with db.transaction(), self.assertRaises(ValueError):
                storage.record_event(
                    db, self.character["id"], "fight:7", {"breeds": [2]}
                )
        with self.store.connection() as db:
            self.assertEqual(storage.load_locked(db, self.character["id"]), state)
            authority = db.execute(
                "SELECT snapshot FROM character_achievement_authority WHERE character_id=%s",
                (self.character["id"],),
            ).fetchone()["snapshot"]
            self.assertEqual(authority["completed"], [238])
        with self.assertRaisesRegex(RuntimeError, "rollback"):
            with self.store.connection() as db:
                storage.record_event(
                    db, self.character["id"], "fight:8", {"breeds": [2]}
                )
                storage.store(
                    db, self.character["id"], dict(state, variables={"51": 99})
                )
                raise RuntimeError("rollback")
        with self.store.connection() as db:
            self.assertEqual(storage.load_locked(db, self.character["id"]), state)
            self.assertTrue(
                storage.record_event(
                    db, self.character["id"], "fight:8", {"breeds": [2]}
                )
            )

    def test_reward_pending_delivery_and_notification_replay(self):
        reward = dict(d=1, aeV=5, ckl=[2021, 1])
        with self.store.connection() as db:
            self.assertTrue(
                storage.claim_reward(db, self.character["id"], 238, "once", 1, reward)
            )
            self.assertFalse(
                storage.claim_reward(db, self.character["id"], 238, "once", 1, reward)
            )
            self.assertEqual(len(storage.pending_rewards(db, self.character["id"])), 1)
            storage.mark_reward_delivered(db, self.character["id"], 238, "once", 1)
            self.assertEqual(storage.pending_rewards(db, self.character["id"]), [])
            packets = [dict(opcode=13295, payload_hex="0102")]
            self.assertTrue(
                storage.enqueue_notifications(
                    db, self.character["id"], "fight:1", packets
                )
            )
            self.assertFalse(
                storage.enqueue_notifications(
                    db, self.character["id"], "fight:1", packets
                )
            )
            self.assertEqual(
                len(storage.pending_notifications(db, self.character["id"])), 1
            )
            storage.mark_notifications_delivered(db, self.character["id"], "fight:1")
            self.assertEqual(
                storage.pending_notifications(db, self.character["id"]), []
            )
            with self.assertRaises(ValueError):
                storage.enqueue_notifications(
                    db,
                    self.character["id"],
                    "fight:1",
                    [dict(opcode=13295, payload_hex="0304")],
                )

    def test_offline_owned_item_reward_and_capacity_failure_do_not_allocate(self):
        with self.store.connection() as db:
            # Earned offline rewards require owned character authority, not a selected lease.
            service._owner(db, self.character)
            packets = rewards.grant(
                db, self.store, self.character, dict(aeV=5, ckl=[2021, 1])
            )
            self.assertEqual([op for op, _ in packets], [12471])
            current = self.store.character(self.account, self.character["id"], db)
            self.assertEqual(len(current["inventory_items"]), 1)
            # Reducing only the test bag capacity avoids generating hundreds of units.
            db.execute(
                "UPDATE inventory_containers SET capacity=1 WHERE character_id=%s AND kind=0",
                (self.character["id"],),
            )
            before = db.execute(
                "SELECT count(*) AS n FROM inventory_items WHERE character_id=%s",
                (self.character["id"],),
            ).fetchone()["n"]
            with self.assertRaises(rewards.RewardCapacity):
                rewards.grant(db, self.store, current, dict(aeV=5, ckl=[2021, 1]))
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM inventory_items WHERE character_id=%s",
                    (self.character["id"],),
                ).fetchone()["n"],
                before,
            )
            with self.assertRaises(ValueError):
                service._owner(db, dict(self.character, account_id=self.account + 9999))

    def test_actual_settlement_completes_once_grants_and_replays_offline(self):
        from types import SimpleNamespace

        with self.store.connection() as db:
            fight_id = db.execute(
                "INSERT INTO combat_fights(status,fight_kind) VALUES('finished','pve') RETURNING id"
            ).fetchone()["id"]
            db.execute(
                "INSERT INTO combat_fight_participants(fight_id,character_id,account_id,team) VALUES(%s,%s,%s,0)",
                (fight_id, self.character["id"], self.account),
            )
        actors = {
            self.character["id"]: SimpleNamespace(
                controlled=True, owner_id=self.account, team=0, hp=1
            )
        }
        roster = []
        for identity, breed in ((-1, 39), (-2, 2), (-3, 1)):
            actors[identity] = SimpleNamespace(controlled=False, team=1, hp=0)
            roster.append(dict(id=identity, ref=breed))
        fight = SimpleNamespace(
            id=fight_id,
            phase="finished",
            winner=0,
            actors=actors,
            native_summon_registrations={},
        )
        with self.store.connection() as db:
            first = service.settle(db, self.store, self.character, fight, roster)
            self.assertFalse(first["replay"])
            self.assertIn(
                238, storage.load_locked(db, self.character["id"])["completed"]
            )
            self.assertEqual(
                len(storage.pending_notifications(db, self.character["id"])), 1
            )
            self.assertEqual(storage.pending_rewards(db, self.character["id"]), [])
            current = self.store.character(self.account, self.character["id"], db)
            self.assertEqual(
                [
                    (row["reference"], row["quantity"])
                    for row in current["inventory_items"]
                ],
                [(7361, 5)],
            )
            replay = service.settle(db, self.store, self.character, fight, roster)
            self.assertTrue(replay["replay"])
            self.assertEqual(replay["packets"], [])
            self.assertEqual(
                storage.load_locked(db, self.character["id"])["variables"],
                {"51": 1, "52": 1, "53": 1},
            )
            service.track(db, self.character, 239, True)
            self.assertEqual(
                storage.load_locked(db, self.character["id"])["tracking"], [239]
            )
            self.assertTrue(service.snapshot(db, self.character["id"]))

    def test_capacity_keeps_completion_and_pending_reward_until_real_slot_is_freed(
        self,
    ):
        from types import SimpleNamespace
        import struct
        from wakfu_server import inventory_actions

        generation = self.store.begin_session(self.account)
        self.store.select_character(self.account, generation, self.character["id"])
        with self.store.connection() as db:
            db.execute(
                "UPDATE inventory_containers SET capacity=1 WHERE character_id=%s AND kind=0",
                (self.character["id"],),
            )
            rewards.grant(db, self.store, self.character, dict(aeV=5, ckl=[2021, 1]))
            occupied = self.store.character(self.account, self.character["id"], db)[
                "inventory_items"
            ][0]["uid"]
            fight_id = db.execute(
                "INSERT INTO combat_fights(status,fight_kind) VALUES('finished','pve') RETURNING id"
            ).fetchone()["id"]
            db.execute(
                "INSERT INTO combat_fight_participants(fight_id,character_id,account_id,team) VALUES(%s,%s,%s,0)",
                (fight_id, self.character["id"], self.account),
            )
        actors = {
            self.character["id"]: SimpleNamespace(
                controlled=True, owner_id=self.account, team=0, hp=1
            )
        }
        roster = []
        for identity, breed in ((-1, 39), (-2, 2), (-3, 1)):
            actors[identity] = SimpleNamespace(controlled=False, team=1, hp=0)
            roster.append(dict(id=identity, ref=breed))
        fight = SimpleNamespace(
            id=fight_id,
            phase="finished",
            winner=0,
            actors=actors,
            native_summon_registrations={},
        )
        with self.store.connection() as db:
            result = service.settle(db, self.store, self.character, fight, roster)
            self.assertFalse(result["replay"])
            self.assertIn(
                238, storage.load_locked(db, self.character["id"])["completed"]
            )
            self.assertEqual(len(storage.pending_rewards(db, self.character["id"])), 1)
            self.assertEqual(service.drain_rewards(db, self.store, self.character), [])
        inventory_actions.destroy(
            self.store,
            self.account,
            generation,
            self.character["id"],
            struct.pack(">q", occupied),
        )
        with self.store.connection() as db:
            self.assertEqual(
                [op for op, _ in service.drain_rewards(db, self.store, self.character)],
                [12471],
            )
            self.assertEqual(storage.pending_rewards(db, self.character["id"]), [])
            self.assertEqual(service.drain_rewards(db, self.store, self.character), [])
            self.assertTrue(
                service.settle(db, self.store, self.character, fight, roster)["replay"]
            )
            self.assertEqual(
                storage.load_locked(db, self.character["id"])["variables"],
                {"51": 1, "52": 1, "53": 1},
            )
            items = self.store.character(self.account, self.character["id"], db)[
                "inventory_items"
            ]
            self.assertEqual(
                [(row["reference"], row["quantity"]) for row in items], [(7361, 5)]
            )

    def test_bootstrap_captures_keys_without_acknowledging_later_events(self):
        with self.store.connection() as db:
            packets = [dict(opcode=13295, payload_hex="0102")]
            storage.enqueue_notifications(
                db, self.character["id"], "before-bootstrap", packets
            )
            captured = service.bootstrap(db, self.character)
            self.assertEqual(captured["covered_notifications"], ["before-bootstrap"])
            self.assertEqual(
                len(storage.pending_notifications(db, self.character["id"])), 1
            )
            storage.enqueue_notifications(
                db, self.character["id"], "after-bootstrap", packets
            )
            service.acknowledge_notifications(
                db, self.character, captured["covered_notifications"]
            )
            self.assertEqual(
                [
                    row["event_key"]
                    for row in storage.pending_notifications(db, self.character["id"])
                ],
                ["after-bootstrap"],
            )
            batches = service.notification_batches(db, self.character)
            self.assertEqual(
                batches, [dict(key="after-bootstrap", packets=[(13295, b"\x01\x02")])]
            )

    def test_title_reward_is_idempotent_and_unsupported_reward_mutates_nothing(self):
        with self.store.connection() as db:
            service._owner(db, self.character)
            reward = dict(aeV=2, ckl=[9])
            rewards.grant(db, self.store, self.character, reward)
            first = db.execute(
                "SELECT record FROM account_cosmetics WHERE account_id=%s",
                (self.account,),
            ).fetchone()["record"]
            rewards.grant(db, self.store, self.character, reward)
            self.assertEqual(
                db.execute(
                    "SELECT record FROM account_cosmetics WHERE account_id=%s",
                    (self.account,),
                ).fetchone()["record"],
                first,
            )
            with self.assertRaises(ValueError):
                rewards.grant(db, self.store, self.character, dict(aeV=99, ckl=[]))
            self.assertEqual(
                db.execute(
                    "SELECT record FROM account_cosmetics WHERE account_id=%s",
                    (self.account,),
                ).fetchone()["record"],
                first,
            )


if __name__ == "__main__":
    unittest.main()
