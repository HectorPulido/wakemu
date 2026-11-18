"""Sidecar and accepted checkpoint share the actual SQL CAS/rollback boundary."""

from copy import deepcopy
from unittest.mock import patch

from postgres_case import PostgresCase
from test_combat_rewards import setup_reward_state
from test_native_order_trial_checkpoint import prepared_fixture, stage_fixture
from wakfu_server.fight_checkpoint_store import Checkpoints
from wakfu_server.native_order_trial_checkpoint import FIELD


class NativeOrderTrialCheckpointPostgresTests(PostgresCase):
    def test_accepted_checkpoint_and_native_receipts_commit_or_rollback_together(self):
        store, account, character, generation, fight = setup_reward_state(self.store)
        prepared_fixture(fight, generation=generation)
        with store.connection() as db:
            db.execute(
                "UPDATE combat_fights SET status='active' WHERE id=%s", (fight.id,)
            )
        checkpoints = Checkpoints(store)
        first = checkpoints.save(account, generation, fight)
        original = checkpoints.read(account, fight.id)
        candidate = deepcopy(fight)
        self.assertTrue(stage_fixture(candidate, "spawn", target_id=-301, color="blue"))
        with patch(
            "wakfu_server.combat_captured_roster_checkpoint.persist_captured_roster_updates",
            side_effect=RuntimeError("post-write failure"),
        ):
            with self.assertRaisesRegex(RuntimeError, "post-write failure"):
                checkpoints.save(
                    account, generation, candidate, expected_revision=first
                )
        rolled_back = checkpoints.read(account, fight.id)
        self.assertEqual(rolled_back["revision"], first)
        self.assertEqual(rolled_back["snapshot"][FIELD], original["snapshot"][FIELD])
        second = checkpoints.save(
            account, generation, candidate, expected_revision=first
        )
        accepted = checkpoints.read(account, fight.id)
        self.assertEqual(second, first + 1)
        self.assertEqual(accepted["snapshot"][FIELD], candidate.native_order_trial)
        with self.assertRaisesRegex(ValueError, "Stale"):
            checkpoints.save(account, generation, fight, expected_revision=first)
        self.assertEqual(
            checkpoints.read(account, fight.id)["snapshot"][FIELD],
            accepted["snapshot"][FIELD],
        )
