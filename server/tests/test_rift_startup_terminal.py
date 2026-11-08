"""Actual PostgreSQL startup settlement and authenticated terminal return."""
import unittest
from unittest.mock import patch
from postgres_case import PostgresCase
import test_rift_earned_rewards as earned_fixtures
from wakfu_server import combat_rewards, fight_store, rift_runtime, reward_policy
from wakfu_server.progression import level_xp
from wakfu_server.combat_encounter_roles import assigned_roles


class StartupTerminalTests(PostgresCase):
    _company = earned_fixtures.RiftEarnedRewardTests._company
    _fixture = earned_fixtures.RiftEarnedRewardTests._fixture
    _interrupted_checkpoint = (
        earned_fixtures.RiftEarnedRewardTests._interrupted_checkpoint
    )

    def scenario(self, *, won=False, no_kills=False):
        run, fight, original, checkpoints, revision = self._interrupted_checkpoint(
            no_kills=no_kills
        )
        roles = assigned_roles(fight)
        fight.phase = "finished"
        fight.winner = roles.player_team if won else roles.npc_team
        fight.native_timeline_round = run["policy"]["turn_budget"] if won else 7
        # Actual terminal accounting fixture: all owners KO on loss; a hero KO
        # on win. Native lethal handling is covered elsewhere, not replayed here.
        for identity in self.ids:
            fight.actors[identity].hp = original[identity]["hp"] if won else 0
        fight.actors[self.ids[1]].hp = 0
        with self.store.connection() as db:
            db.execute(
                "UPDATE character_progression SET xp=%s WHERE character_id=ANY(%s)",
                (level_xp(31) - 1, self.ids),
            )
        revision = checkpoints.save(
            self.account, self.generation, fight, expected_revision=revision
        )
        killed = sorted(i for i in fight.rift_monsters if fight.actors[i].hp <= 0)
        before = {i: self.store.character(self.account, i) for i in self.ids}
        if not no_kills:
            award = combat_rewards.award_shared_member

            def reject_after_award(*args, **kwargs):
                award(*args, **kwargs)
                raise RuntimeError("startup terminal rollback witness")

            with patch.object(
                combat_rewards, "award_shared_member", reject_after_award
            ):
                with self.assertRaisesRegex(
                    ValueError, "startup terminal rollback witness"
                ):
                    checkpoints.recover_interrupted()
            with self.store.connection() as db:
                self.assertEqual(
                    rift_runtime._run(db, run["instance_id"])["status"], "running"
                )
                self.assertEqual(
                    db.execute(
                        "SELECT status FROM combat_fights WHERE id=%s", (fight.id,)
                    ).fetchone()["status"],
                    "active",
                )
                for table in (
                    "fight_rewards",
                    "fight_health_exits",
                    "rift_item_reward_receipts",
                ):
                    self.assertEqual(
                        db.execute(
                            "SELECT count(*) AS n FROM " + table + " WHERE fight_id=%s",
                            (fight.id,),
                        ).fetchone()["n"],
                        0,
                    )
                self.assertIsNone(
                    db.execute(
                        "SELECT 1 FROM rift_settlement_receipts WHERE instance_id=%s",
                        (run["instance_id"],),
                    ).fetchone()
                )
            self.assertEqual(
                {i: self.store.character(self.account, i) for i in self.ids}, before
            )
        checkpoints.recover_interrupted()
        with self.store.connection() as db:
            receipt = db.execute(
                "SELECT * FROM rift_settlement_receipts WHERE instance_id=%s",
                (run["instance_id"],),
            ).fetchone()
            self.assertEqual(receipt["outcome"], "won" if won else "lost")
            self.assertEqual(
                receipt["result"]["recovery"]["defeated_actor_ids"], killed
            )
            self.assertEqual(
                receipt["result"]["recovery"]["checkpoint_winner"], fight.winner
            )
            self.assertEqual(
                db.execute(
                    "SELECT status FROM combat_fights WHERE id=%s", (fight.id,)
                ).fetchone()["status"],
                "finished",
            )
            snapshot = db.execute(
                "SELECT snapshot FROM fight_checkpoints WHERE fight_id=%s", (fight.id,)
            ).fetchone()["snapshot"]
            self.assertEqual(
                (snapshot["phase"], snapshot["winner"]), ("finished", fight.winner)
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM fight_health_exits WHERE fight_id=%s",
                    (fight.id,),
                ).fetchone()["n"],
                0,
                "startup must not invent a return ACK",
            )
            rewards = list(
                db.execute(
                    "SELECT * FROM fight_rewards WHERE fight_id=%s ORDER BY character_id",
                    (fight.id,),
                )
            )
            self.assertEqual(len(rewards), 0 if no_kills and not won else len(self.ids))
            if not no_kills:
                self.assertTrue(
                    all(
                        row["xp"] > 0 and row["end_level"] > row["start_level"]
                        for row in rewards
                    )
                )
                for row in db.execute(
                    "SELECT snapshot FROM fight_reward_policy_receipts WHERE fight_id=%s",
                    (fight.id,),
                ):
                    self.assertEqual(
                        sorted(
                            m["actor_id"]
                            for m in row["snapshot"]["defeated_native_monsters"]
                        ),
                        killed,
                    )
        settled = {i: self.store.character(self.account, i) for i in self.ids}
        with patch.object(
            reward_policy.secrets, "randbelow", side_effect=AssertionError("reroll")
        ):
            self.assertEqual(checkpoints.recover_interrupted(), 0)
        self.assertEqual(
            {i: self.store.character(self.account, i) for i in self.ids}, settled
        )
        replacement = self.store.begin_session(self.account)
        self.store.select_character(self.account, replacement, self.ids[0])
        found = fight_store.recoverable_finished_fight(
            self.store, self.account, self.ids[0]
        )
        self.assertEqual(
            found, dict(fight_id=fight.id, previous_generation=self.generation)
        )
        result = fight_store.recover_finished_return(
            self.store,
            self.account,
            replacement,
            self.ids[0],
            None,
            self.store.character(self.account, self.ids[0]),
            previous_generation=self.generation,
            fight_id=fight.id,
        )
        self.assertTrue(result["recovered_from_checkpoint"])
        returned = {i: self.store.character(self.account, i) for i in self.ids}
        for identity, character in returned.items():
            self.assertFalse(character["health_dead"])
            self.assertGreater(character["hp"], 0)
            self.assertEqual(
                (character["map_id"], character.get("instance_id", 0)),
                (before[identity]["map_id"], before[identity].get("instance_id", 0)),
            )
        self.assertIsNone(
            fight_store.recoverable_finished_fight(
                self.store, self.account, self.ids[0]
            )
        )
        repeated = fight_store.recover_finished_return(
            self.store,
            self.account,
            replacement,
            self.ids[0],
            None,
            returned[self.ids[0]],
            previous_generation=self.generation,
            fight_id=fight.id,
        )
        self.assertFalse(repeated["applied"])
        self.assertEqual(
            {i: self.store.character(self.account, i) for i in self.ids}, returned
        )
        with self.store.connection() as db:
            self.assertEqual(
                list(
                    db.execute(
                        "SELECT * FROM fight_rewards WHERE fight_id=%s ORDER BY character_id",
                        (fight.id,),
                    )
                ),
                rewards,
            )
            exits = list(
                db.execute(
                    "SELECT reason,return_acknowledged_at FROM fight_health_exits WHERE fight_id=%s",
                    (fight.id,),
                )
            )
            self.assertEqual(len(exits), len(self.ids))
            self.assertTrue(
                all(
                    row["reason"] == "return"
                    and row["return_acknowledged_at"] is not None
                    for row in exits
                )
            )
            generations = list(
                db.execute(
                    "SELECT session_generation FROM combat_fight_participants WHERE fight_id=%s",
                    (fight.id,),
                )
            )
            self.assertTrue(
                all(row["session_generation"] == replacement for row in generations)
            )

    def test_loss_partial_kills_rollback_once_ko_levelup_new_lease_return(self):
        self.scenario()

    def test_win_preserves_outcome_and_return(self):
        self.scenario(won=True)

    def test_zero_kill_loss_preserves_outcome_without_awards(self):
        self.scenario(no_kills=True)


if __name__ == "__main__":
    unittest.main()
