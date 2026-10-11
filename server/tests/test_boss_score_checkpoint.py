"""Actual PostgreSQL checkpoint replay after terminal score and reward commit."""
from postgres_case import PostgresCase
from test_combat_rewards import setup_reward_state
from wakfu_server.fight_checkpoint_store import Checkpoints
from wakfu_server.combat_rewards import award, Policy
from wakfu_server.maps import boss_score, boss_score_runtime


class BossScoreCheckpointTests(PostgresCase):
    def test_terminal_reward_then_checkpoint_preserves_damage_receipts(self):
        store, account, character, generation, fight = setup_reward_state(self.store)
        with store.connection() as db:
            profile = boss_score.freeze(
                db,
                fight.id,
                monsters={-200: {"ref": 4378, "team": 1}},
                player_ids=[character["id"]],
            )
        fight.boss_score_profile = profile
        fight.native_timeline_round = 21
        event = dict(
            event_id="action:runner:boss",
            source_id=character["id"],
            target_id=-200,
            owner_actor_id=character["id"],
            post_mitigation_damage=100,
            armor_absorbed=20,
            round_number=20,
            source_is_registered_summon=False,
        )
        fight.boss_score_events = {event["event_id"]: event}
        checkpoints = Checkpoints(store)
        first = checkpoints.save(account, generation, fight)
        with store.connection() as db:
            result = boss_score_runtime.finalize(db, fight)
            self.assertEqual(120, result["score"])
            award(
                store,
                account,
                generation,
                character["id"],
                fight,
                Policy(xp=0, kamas=0),
                db=db,
            )
        # The real save_prepared path flushes these same events after finalize.
        second = checkpoints.save(account, generation, fight, expected_revision=first)
        self.assertEqual(first + 1, second)
        with store.connection() as db:
            self.assertEqual(
                1,
                db.execute(
                    "SELECT count(*) AS n FROM boss_score_damage_receipts WHERE fight_id=%s",
                    (fight.id,),
                ).fetchone()["n"],
            )
            self.assertEqual(
                120,
                db.execute(
                    "SELECT score FROM boss_score_terminal_receipts WHERE fight_id=%s",
                    (fight.id,),
                ).fetchone()["score"],
            )
