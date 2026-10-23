"""Profile/accounting premises, separate from the real Ogrest scene acceptance."""
from types import SimpleNamespace
import unittest

from postgres_case import PostgresCase
from wakfu_server.combat_boss_score_policy import OGREST_SCORE, native_score_policy
from wakfu_server.combat_ogrest_score_policy import install_ogrest_score_profile
from wakfu_server.combat_npc_phase_controller import deliver_npc_score_result
from wakfu_server.maps import boss_score
from wakfu_server.maps.boss_score_runtime import (
    finish_survival,
    stage_damage,
    staged_score,
)


class OgrestScoreProfileTests(unittest.TestCase):
    def test_owned_director_profile_separates_exit_victory_from_loot_and_survival(self):
        player = SimpleNamespace(id=7, team=0, controlled=True)
        boss = SimpleNamespace(id=-200, team=1, controlled=False)
        context = dict(policy=OGREST_SCORE.name, boss_id=-200)
        fight = SimpleNamespace(
            actors={7: player, -200: boss},
            phase="active",
            turn_id=1,
            native_start_event_delivered=True,
            native_ogrest_phase_context=context,
            native_timeline_round=1,
        )
        dispatcher = SimpleNamespace(native_retention=SimpleNamespace(fight=fight))
        profile = install_ogrest_score_profile(dispatcher, context)
        self.assertEqual(native_score_policy(profile), OGREST_SCORE)
        self.assertEqual(
            (
                profile["minimum_score"],
                profile["loot_minimum_score"],
                profile["round_limit"],
            ),
            (0, 1000000, 18),
        )
        self.assertFalse(deliver_npc_score_result(dispatcher, actor_id=7))
        fight.native_timeline_round = 19
        self.assertFalse(finish_survival(fight))
        self.assertEqual(fight.phase, "active")
        original = fight.boss_score_profile
        fight.boss_score_profile = dict(
            bosses={"-200": dict(reference=4378)}, round_limit=20
        )
        fight.native_timeline_round = 21
        self.assertFalse(finish_survival(fight))
        self.assertEqual(fight.phase, "active")
        fight.boss_score_profile = original
        fight.native_timeline_round = 19
        stage_damage(
            fight,
            action_id=1,
            runner_uid=1,
            source=player,
            target=boss,
            result=dict(hp_requested=1000000, virtual_hp_absorbed=0, armor_absorbed=0),
        )
        self.assertEqual(
            staged_score(fight), 0
        )  # Scoring is reconstructed as six three-table phases.


class OgrestDurableScoreTests(PostgresCase):
    def test_exit_authority_and_loot_threshold_are_independent_accounting_premises(
        self,
    ):
        account = self.store.register("ogrest-score", "local-password")["id"]
        identity = self.store.create_character(account, "OgrestScoreWitness")["id"]
        for amount in (0, 999999, 1000000):
            with self.store.connection() as db:
                fight_id = db.execute(
                    "INSERT INTO combat_fights(status) VALUES('active') RETURNING id"
                ).fetchone()["id"]
                boss_score.freeze_snapshot(
                    db,
                    fight_id,
                    dict(
                        policy=boss_score.POLICY,
                        encounter_controller=OGREST_SCORE.name,
                        bosses={"-200": dict(reference=4378)},
                        player_ids=[identity],
                        player_team=0,
                        round_limit=18,
                        minimum_score=0,
                        loot_minimum_score=1000000,
                        terminal_table_limit=20,
                        terminal_source=OGREST_SCORE.terminal_source,
                    ),
                )
                boss_score.record_damage(
                    db,
                    fight_id,
                    event_id="explicit-accounting-premise",
                    source_id=identity,
                    target_id=-200,
                    owner_actor_id=identity,
                    post_mitigation_damage=amount,
                    armor_absorbed=0,
                    round_number=18,
                )
                db.execute(
                    "UPDATE combat_fights SET status='finished' WHERE id=%s",
                    (fight_id,),
                )
            with self.assertRaisesRegex(
                ValueError, "earned terminal exit"
            ), self.store.connection() as db:
                boss_score.finalize(
                    db,
                    fight_id,
                    completed_rounds=18,
                    survived=True,
                    winning_team=0,
                    boss_defeated=False,
                )
            terminal = dict(
                policy=OGREST_SCORE.name,
                result="victory",
                boss_id=-200,
                actor_id=identity,
                table=19,
                source="actual_owned_player_turn_end",
                area_reference=1255,
                score=amount,
            )
            with self.store.connection() as db:
                result = boss_score.finalize(
                    db,
                    fight_id,
                    completed_rounds=18,
                    survived=True,
                    winning_team=0,
                    boss_defeated=False,
                    terminal_authority=terminal,
                )
                self.assertEqual(result["winning_team"], 0)
                self.assertEqual(result["eligible"], amount >= 1000000)
                self.assertEqual(result["score"], amount)
                self.assertFalse(result["boss_defeated"])
                self.assertEqual(result["native_terminal_authority"], terminal)
                self.assertEqual(
                    boss_score.drop_context(db, fight_id),
                    {"score": amount} if amount >= 1000000 else {},
                )
