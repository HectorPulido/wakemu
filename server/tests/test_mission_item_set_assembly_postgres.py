"""Journal item assembly advances only a running, level-qualified mission."""
import struct
import unittest
from unittest.mock import patch

from postgres_case import PostgresCase
from wakfu_server import journal_part_item_actions as journal_actions
from wakfu_server.achievements import storage as achievement_storage
from wakfu_server.inventory_items import grant
from wakfu_server.progression import level_xp


class MissionItemSetAssemblyPostgresTests(PostgresCase):
    def _fixture(self, *, level=178, running=True):
        account = self.store.register("mission-assembly", "local-password")["id"]
        character = self.store.create_character(account, "Mission Assembly")
        generation = self.store.begin_session(account)
        self.store.select_character(account, generation, character["id"])
        with self.store.connection() as db:
            db.execute(
                "UPDATE characters SET level=%s WHERE id=%s",
                (level, character["id"]),
            )
            db.execute(
                "UPDATE character_progression SET xp=%s WHERE character_id=%s",
                (level_xp(level), character["id"]),
            )
            state = achievement_storage.load_locked(db, character["id"])
            if running:
                state["running"] = sorted(set(state["running"]) | {2907})
                state["tracking"] = sorted(set(state["tracking"]) | {2907})
            achievement_storage.store(db, character["id"], state)
        return account, generation, character["id"]

    def _group_inputs(self, account, generation, character_id, group, *, count=1):
        character = self.store.character(account, character_id)
        bag = next(row for row in character["inventory_containers"] if row["kind"] == 0)
        with self.store.connection() as db:
            occupied = {
                row["slot"]
                for row in db.execute(
                    "SELECT slot FROM inventory_items WHERE container=%s", (bag["uid"],)
                )
            }
        available = [slot for slot in range(bag["capacity"]) if slot not in occupied]
        items = []
        for _ in range(count):
            for reference in group["input_references"]:
                if not available:
                    raise AssertionError("test fixture exhausted the character bag")
                slot = available.pop(0)
                items.append(
                    grant(
                        self.store,
                        account,
                        generation,
                        character_id,
                        reference=reference,
                        quantity=1,
                        container=bag["uid"],
                        slot=slot,
                        allowed_references={reference},
                    )
                )
                slot += 1
        return items

    @staticmethod
    def _body(group, item):
        action = next(
            row["action_id"]
            for row in group["items"]
            if row["item_ref"] == item["reference"]
        )
        return struct.pack(">iq", action, item["uid"])

    def _running_state(self, account, character_id):
        with self.store.connection() as db:
            state = achievement_storage.load_locked(db, character_id)
        return state

    def test_three_real_groups_complete_running_mission_once_and_replay_is_idempotent(
        self,
    ):
        account, generation, character_id = self._fixture()
        groups = journal_actions.descriptors()["groups"]
        receipt_ids = []
        results = []
        for group in groups:
            inputs = self._group_inputs(account, generation, character_id, group)
            result = journal_actions.use(
                self.store,
                account,
                generation,
                character_id,
                self._body(group, inputs[0]),
                in_fight=False,
            )
            receipt_ids.append(result["assembly_receipt_id"])
            results.append(result)

        self.assertEqual(
            [row["mission_result"]["new_objectives"] for row in results],
            [[5923], [5911], [5912]],
        )
        self.assertEqual(
            [row["mission_result"]["completed"] for row in results], [[], [], [2907]]
        )
        self.assertEqual([row["xp_changed"] for row in results], [False, False, True])
        before_xp = level_xp(178)
        self.assertEqual(results[-1]["character"]["xp"], before_xp + 200_000_000)
        state = self._running_state(account, character_id)
        self.assertNotIn(2907, state["running"])
        self.assertIn(2907, state["completed"])
        self.assertEqual(
            set(state["objectives"]) & {5923, 5911, 5912}, {5923, 5911, 5912}
        )

        from wakfu_server.achievements import mission_assembly

        with self.store.connection() as db:
            character = self.store.character(account, character_id, db)
            replay = mission_assembly.settle(db, self.store, character, receipt_ids[-1])
            rewards = list(
                db.execute(
                    "SELECT reward_key,payload,delivered_at FROM character_achievement_reward_outbox "
                    "WHERE character_id=%s AND achievement_id=2907",
                    (character_id,),
                )
            )
        self.assertFalse(replay["xp_changed"])
        self.assertFalse(replay["applied"])
        self.assertEqual(len(rewards), 1)
        self.assertEqual(rewards[0]["reward_key"], "4496")
        self.assertEqual(
            rewards[0]["payload"],
            {"d": 4496, "aeV": 6, "ckk": False, "ckl": [200_000_000]},
        )
        self.assertIsNotNone(rewards[0]["delivered_at"])
        restored = self.reopen().character(account, character_id)
        self.assertEqual(restored["xp"], before_xp + 200_000_000)

    def test_preexisting_objective_flags_and_nonrunning_or_low_level_receipts_do_not_backfill(
        self,
    ):
        account, generation, character_id = self._fixture(level=177, running=True)
        groups = journal_actions.descriptors()["groups"]
        with self.store.connection() as db:
            state = achievement_storage.load_locked(db, character_id)
            state["objectives"] = sorted(set(state["objectives"]) | {5923, 5911, 5912})
            achievement_storage.store(db, character_id, state)

        # First receipt is below level and the mission is not running.
        first = self._group_inputs(
            account, generation, character_id, groups[0], count=2
        )
        early = journal_actions.use(
            self.store,
            account,
            generation,
            character_id,
            self._body(groups[0], first[0]),
            in_fight=False,
        )
        self.assertFalse(early["mission_result"]["applied"])
        self.assertFalse(early["xp_changed"])

        with self.store.connection() as db:
            db.execute("UPDATE characters SET level=178 WHERE id=%s", (character_id,))
            db.execute(
                "UPDATE character_progression SET xp=%s WHERE character_id=%s",
                (level_xp(178), character_id),
            )
            state = achievement_storage.load_locked(db, character_id)
            achievement_storage.store(db, character_id, state)
        second_inputs = self._group_inputs(account, generation, character_id, groups[1])
        third_inputs = self._group_inputs(account, generation, character_id, groups[2])
        second = journal_actions.use(
            self.store,
            account,
            generation,
            character_id,
            self._body(groups[1], second_inputs[0]),
            in_fight=False,
        )
        third = journal_actions.use(
            self.store,
            account,
            generation,
            character_id,
            self._body(groups[2], third_inputs[0]),
            in_fight=False,
        )
        # The objective bits were preseeded, so there are no new deltas; only
        # accredited assembly receipts can satisfy the completion check.
        self.assertEqual(second["mission_result"]["new_objectives"], [])
        self.assertEqual(third["mission_result"]["new_objectives"], [])
        self.assertFalse(third["xp_changed"])
        self.assertFalse(third["mission_result"]["completed"])
        self.assertNotIn(2907, self._running_state(account, character_id)["completed"])

        # A new, real first-group receipt at the qualified level completes it;
        # old objective bits and the early receipt cannot substitute for it.
        retry = journal_actions.use(
            self.store,
            account,
            generation,
            character_id,
            self._body(groups[0], first[len(groups[0]["input_references"])]),
            in_fight=False,
        )
        self.assertEqual(retry["mission_result"]["completed"], [2907])
        self.assertTrue(retry["xp_changed"])

    def test_final_group_grant_failure_rolls_back_inputs_output_receipt_and_progress_for_retry(
        self,
    ):
        account, generation, character_id = self._fixture()
        groups = journal_actions.descriptors()["groups"]
        for group in groups[:2]:
            inputs = self._group_inputs(account, generation, character_id, group)
            journal_actions.use(
                self.store,
                account,
                generation,
                character_id,
                self._body(group, inputs[0]),
                in_fight=False,
            )
        last = groups[2]
        inputs = self._group_inputs(account, generation, character_id, last)
        before_state = self._running_state(account, character_id)
        with patch(
            "wakfu_server.achievements.rewards.grant",
            side_effect=ValueError("test output failure"),
        ):
            with self.assertRaisesRegex(ValueError, "test output failure"):
                journal_actions.use(
                    self.store,
                    account,
                    generation,
                    character_id,
                    self._body(last, inputs[0]),
                    in_fight=False,
                )
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM inventory_items WHERE uid=ANY(%s)",
                    ([item["uid"] for item in inputs],),
                ).fetchone()["n"],
                len(inputs),
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM item_set_assembly_receipts WHERE character_id=%s",
                    (character_id,),
                ).fetchone()["n"],
                2,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM character_achievement_events "
                    "WHERE character_id=%s AND event_key LIKE 'journal-assembly:%%'",
                    (character_id,),
                ).fetchone()["n"],
                2,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM character_achievement_reward_outbox "
                    "WHERE character_id=%s AND achievement_id=2907",
                    (character_id,),
                ).fetchone()["n"],
                0,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM character_quest_items "
                    "WHERE character_id=%s AND reference=20445",
                    (character_id,),
                ).fetchone()["n"],
                0,
            )
        self.assertEqual(self._running_state(account, character_id), before_state)
        completed = journal_actions.use(
            self.store,
            account,
            generation,
            character_id,
            self._body(last, inputs[0]),
            in_fight=False,
        )
        self.assertEqual(completed["mission_result"]["completed"], [2907])
        self.assertTrue(completed["xp_changed"])

    def test_high_level_nonrunning_assemblies_do_not_backfill_after_activation(self):
        account, generation, character_id = self._fixture(level=178, running=False)
        groups = journal_actions.descriptors()["groups"]
        for group in groups:
            inputs = self._group_inputs(account, generation, character_id, group)
            result = journal_actions.use(
                self.store,
                account,
                generation,
                character_id,
                self._body(group, inputs[0]),
                in_fight=False,
            )
            self.assertFalse(result["xp_changed"])
            self.assertFalse(result["mission_result"]["applied"])

        with self.store.connection() as db:
            state = achievement_storage.load_locked(db, character_id)
            state["running"] = [2907]
            state["tracking"] = [2907]
            achievement_storage.store(db, character_id, state)
        self.assertNotIn(2907, self._running_state(account, character_id)["completed"])

        # Fresh receipts created after activation qualify; the older three
        # nonrunning receipts remain ineligible evidence.
        results = []
        for group in groups:
            inputs = self._group_inputs(account, generation, character_id, group)
            results.append(
                journal_actions.use(
                    self.store,
                    account,
                    generation,
                    character_id,
                    self._body(group, inputs[0]),
                    in_fight=False,
                )
            )
        self.assertEqual(
            [row["mission_result"]["completed"] for row in results], [[], [], [2907]]
        )
        self.assertTrue(results[-1]["xp_changed"])

    def test_stale_lease_cannot_assemble_and_foreign_character_cannot_settle_receipt(
        self,
    ):
        account, generation, character_id = self._fixture()
        other_account = self.store.register("mission-assembly-other", "local-password")[
            "id"
        ]
        other = self.store.create_character(other_account, "Other Mission Owner")
        group = journal_actions.descriptors()["groups"][0]
        inputs = self._group_inputs(account, generation, character_id, group)
        body = self._body(group, inputs[0])
        with self.assertRaises(ValueError):
            journal_actions.use(
                self.store, account, "expired-lease", character_id, body, in_fight=False
            )
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM item_set_assembly_receipts WHERE character_id=%s",
                    (character_id,),
                ).fetchone()["n"],
                0,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM inventory_items WHERE uid=ANY(%s)",
                    ([row["uid"] for row in inputs],),
                ).fetchone()["n"],
                len(inputs),
            )

        result = journal_actions.use(
            self.store, account, generation, character_id, body, in_fight=False
        )
        receipt_id = result["assembly_receipt_id"]
        from wakfu_server.achievements import mission_assembly

        with self.store.connection() as db:
            foreign = self.store.character(other_account, other["id"], db)
            with self.assertRaisesRegex(
                ValueError, "Missing owned journal mission assembly receipt"
            ):
                mission_assembly.settle(db, self.store, foreign, receipt_id)
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM character_achievement_events WHERE character_id=%s",
                    (other["id"],),
                ).fetchone()["n"],
                0,
            )
