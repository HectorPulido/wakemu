"""Rolled-back background reward conflicts retain their earned entitlement."""
import ast
from copy import deepcopy
from pathlib import Path
from unittest.mock import Mock, patch

from psycopg.errors import SerializationFailure

from postgres_case import PostgresCase
import test_custom_task_rewards_postgres as reward_cases
from wakfu_server.achievements import rewards
from wakfu_server.custom_tasks import reward_delivery


class CustomTaskBackgroundLockDeferralPostgresTests(PostgresCase):
    earn = reward_cases.CustomTaskRewardsPostgresTests.earn

    def setUp(self):
        super().setUp()
        self.account = self.store.register("background-reward-owner", "local-password")[
            "id"
        ]
        self.character = self.store.create_character(
            self.account, "Background Reward Owner"
        )["id"]
        self.generation = self.store.begin_session(self.account)
        self.store.select_character(self.account, self.generation, self.character)

    def capture_background(self):
        source_path = Path(__file__).resolve().parents[1] / "local_game_server.py"
        tree = ast.parse(source_path.read_text())
        helper = next(
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef)
            and node.name == "deliver_custom_task_rewards"
        )
        factory = ast.parse("def capture(character):\n    pass\n").body[0]
        factory.body = [
            helper,
            *ast.parse("return deliver_custom_task_rewards, lambda: character").body,
        ]
        self.records = []
        self.send = Mock()
        namespace = dict(
            STORE=self.store,
            account_id=self.account,
            generation=self.generation,
            record=lambda **event: self.records.append(event),
            send=self.send,
            connection=object(),
            service="world",
        )
        exec(
            compile(
                ast.fix_missing_locations(ast.Module(body=[factory], type_ignores=[])),
                str(source_path),
                "exec",
            ),
            namespace,
        )
        before = self.store.character(self.account, self.character)
        call, current = namespace["capture"](before)
        return call, current, deepcopy(before)

    def assert_pending_and_empty(self):
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM inventory_items WHERE character_id=%s",
                    (self.character,),
                ).fetchone()["n"],
                0,
            )
            row = db.execute(
                "SELECT delivered_at FROM character_custom_task_reward_outbox "
                "WHERE character_id=%s AND task_key='explicit-test-task' AND reward_index=0",
                (self.character,),
            ).fetchone()
            self.assertIsNotNone(row)
            self.assertIsNone(row["delivered_at"])

    def assert_conflict_defers_after_actual_rollback(self, sqlstate):
        self.earn([dict(aeV=5, ckl=[2021, 1])])
        call, current, before = self.capture_background()
        original_grant = rewards.grant

        def grant_then_abort(db, store, character, reward):
            original_grant(db, store, character, reward)
            if sqlstate == "40P01":
                db.execute(
                    "DO $$BEGIN RAISE EXCEPTION 'test deadlock' USING ERRCODE='40P01'; END$$"
                )
            else:
                db.execute(
                    "DO $$BEGIN RAISE EXCEPTION 'test lock timeout' USING ERRCODE='55P03'; END$$"
                )

        with patch.object(rewards, "grant", side_effect=grant_then_abort) as grant:
            result = call()
            self.assertEqual(grant.call_count, 1, "background delivery retried inline")
        self.assertTrue(result["deferred"])
        self.assertEqual(result["packets"], [])
        self.assertEqual(result["delivered"], [])
        self.assertEqual(current(), before)
        self.send.assert_not_called()
        self.assertTrue(
            self.store.current_character_session(
                self.account, self.generation, self.character
            )
        )
        self.assert_pending_and_empty()
        self.assertEqual(len(self.records), 1)
        self.assertEqual(self.records[0]["event"], "custom_task_rewards_pending")
        self.assertEqual(self.records[0]["sqlstate"], sqlstate)
        self.assertIs(self.records[0]["deferred"], True)

        # A later ordinary delivery consumes the original entitlement once.
        delivered = reward_delivery.deliver(
            self.store, self.account, self.generation, self.character
        )
        self.assertEqual(delivered["delivered"], [("explicit-test-task", 0)])
        replay = reward_delivery.deliver(
            self.store, self.account, self.generation, self.character
        )
        self.assertEqual(replay["delivered"], [])
        self.assertEqual(replay["packets"], [])
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM inventory_items WHERE character_id=%s",
                    (self.character,),
                ).fetchone()["n"],
                1,
            )

    def test_deadlock_rolls_back_then_defers_without_consuming_entitlement(self):
        self.assert_conflict_defers_after_actual_rollback("40P01")

    def test_lock_timeout_rolls_back_then_defers_without_consuming_entitlement(self):
        self.assert_conflict_defers_after_actual_rollback("55P03")

    def test_other_database_error_propagates_after_rollback(self):
        self.earn([dict(aeV=5, ckl=[2021, 1])])
        call, current, before = self.capture_background()
        original_grant = rewards.grant

        def grant_then_abort(db, store, character, reward):
            original_grant(db, store, character, reward)
            db.execute(
                "DO $$BEGIN RAISE EXCEPTION 'test serialization failure' USING ERRCODE='40001'; END$$"
            )

        with patch.object(rewards, "grant", side_effect=grant_then_abort):
            with self.assertRaises(SerializationFailure):
                call()
        self.assertEqual(current(), before)
        self.send.assert_not_called()
        self.assertEqual(self.records, [])
        self.assert_pending_and_empty()

    def test_replaced_lease_is_not_treated_as_a_valid_background_deferral(self):
        self.earn([dict(aeV=5, ckl=[2021, 1])])
        call, current, before = self.capture_background()
        replacement = self.store.begin_session(self.account)
        with self.assertRaises(ValueError):
            call()
        self.assertEqual(current(), before)
        self.send.assert_not_called()
        self.assertEqual(self.records, [])
        self.assertTrue(self.store.current_session(self.account, replacement))
        self.assert_pending_and_empty()
