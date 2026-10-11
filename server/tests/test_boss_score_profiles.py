"""Additional local profiles, native threshold and real three-round lifecycle."""
from pathlib import Path
from psycopg.types.json import Jsonb
from postgres_case import PostgresCase
from wakfu_server.combat_state import Actor, Fight
from wakfu_server.maps import boss_score, boss_score_runtime
from wakfu_server.combat_drops import _condition_matches


class BossScoreProfileTests(PostgresCase):
    def setUp(self):
        super().setUp()
        self.account = self.store.register("remaining-score", "local-password")["id"]
        self.cid = self.store.create_character(self.account, "ScoreProfiles")["id"]

    def encounter(self, reference):
        with self.store.connection() as db:
            identity = db.execute(
                "INSERT INTO combat_fights(status) VALUES('active') RETURNING id"
            ).fetchone()["id"]
            db.execute(
                "INSERT INTO combat_fight_participants(fight_id,character_id,account_id,team) VALUES(%s,%s,%s,0)",
                (identity, self.cid, self.account),
            )
            profile = boss_score.prepare_snapshot(
                db,
                identity,
                monsters={-1: {"ref": reference, "team": 1}},
                player_ids=[self.cid],
            )
        return identity, profile

    def test_neoogrest_and_all_native_score_species_have_configured_profiles(self):
        _, profile = self.encounter(5806)
        self.assertEqual(20, profile["round_limit"])
        self.assertEqual(5806, profile["bosses"]["-1"]["reference"])
        with self.store.connection() as db:
            profiles = db.execute(
                "SELECT value FROM settings WHERE name='boss_score_policy'"
            ).fetchone()["value"]["profiles"]
            self.assertEqual({"4378", "5306", "5806", "5608"}, set(profiles))

    def test_love_boss_window_real_three_rounds_and_native_score_boundary(self):
        identity, profile = self.encounter(5608)
        actors = [
            Actor(self.cid, 0, (0, 0, 0), 20, 6, 3, 100, 30, self.account, True),
            Actor(-1, 1, (2, 0, 0), 1000000, 5, 4, 0, 30),
        ]
        fight = Fight(
            identity,
            actors,
            {(x, 0, 0) for x in range(3)},
            {0: {(0, 0, 0)}, 1: {(2, 0, 0)}},
        )
        boss_score_runtime.install(fight, profile)
        fight.ready(self.account)
        fight.native_timeline_round = 1
        boss_score_runtime.stage_damage(
            fight,
            action_id=1,
            runner_uid=1,
            source=actors[0],
            target=actors[1],
            result=dict(hp_requested=14900, virtual_hp_absorbed=0, armor_absorbed=100),
        )
        for number in range(1, 4):
            fight.end_turn(self.account, self.cid, fight.actors[self.cid].turn_count)
            self.assertEqual("active", fight.phase)
            fight.end_server_turn(-1, fight.turn_id)
            self.assertEqual("finished" if number == 3 else "active", fight.phase)
        self.assertEqual(0, fight.winner)
        self.assertEqual(1000000, actors[1].hp)
        with self.store.connection() as db:
            db.execute(
                "UPDATE combat_fights SET status='finished' WHERE id=%s", (identity,)
            )
            result = boss_score_runtime.finalize(db, fight)
            self.assertEqual(15000, result["score"])
            condition = dict(native_enum="MIN_SCORE", value=15000)
            self.assertFalse(_condition_matches(condition, {"score": 14999}))
            self.assertTrue(
                _condition_matches(condition, boss_score.drop_context(db, identity))
            )

    def test_additive_migration_preserves_operator_profiles_on_replay(self):
        path = (
            Path(__file__).resolve().parents[1]
            / "migrations/140_complete_boss_score_profiles.sql"
        )
        with self.store.connection() as db:
            policy = db.execute(
                "SELECT value FROM settings WHERE name='boss_score_policy'"
            ).fetchone()["value"]
            policy["profiles"]["5806"] = {"round_limit": 7, "operator_note": "preserve"}
            db.execute(
                "UPDATE settings SET value=%s WHERE name='boss_score_policy'",
                (Jsonb(policy),),
            )
            db.execute(path.read_text())
            saved = db.execute(
                "SELECT value FROM settings WHERE name='boss_score_policy'"
            ).fetchone()["value"]
            self.assertEqual(policy, saved)

    def damage_fight(self, reference):
        from wakfu_server.combat_damage_handler import (
            NativeDamageHandler,
            DamageExecutionContext,
        )
        from wakfu_server.combat_effect_dispatch import EffectInvocation

        identity, profile = self.encounter(reference)
        actors = [
            Actor(self.cid, 0, (0, 0, 0), 20, 6, 3, 100, 30, self.account, True),
            Actor(-1, 1, (2, 0, 0), 1000000, 5, 4, 0, 30),
        ]
        fight = Fight(
            identity,
            actors,
            {(x, 0, 0) for x in range(3)},
            {0: {(0, 0, 0)}, 1: {(2, 0, 0)}},
        )
        boss_score_runtime.install(fight, profile)
        fight.ready(self.account)
        fight.native_timeline_round = 1
        for actor in actors:
            actor.effect_stats = {92: 0, 97: 0, 100: 0}
            actor.effect_maxima = {92: 0}
            actor.effect_frozen = frozenset()
            actor.physical_radius = 0
        handler = NativeDamageHandler(
            fight,
            [],
            action_id=1,
            allocate_uid=lambda: 99,
            rng=lambda: 0.99,
            context=lambda *args: DamageExecutionContext(
                False, True, False, True, 11, False
            ),
        )
        effect = dict(
            effect_class=1,
            parameters=[1000000, 0],
            native_effect_flags=[],
            native_localization_enabled=True,
        )
        invocation = EffectInvocation(339483, 30, self.cid, -1, (2, 0, 0))
        return fight, handler, effect, invocation

    def test_real_early_love_kill_scores_atomically_and_replays(self):
        fight, handler, effect, invocation = self.damage_fight(5608)
        self.assertTrue(handler(effect, {}, invocation))
        self.assertEqual(
            ("finished", 0, 0), (fight.phase, fight.winner, fight.actors[-1].hp)
        )
        with self.assertRaisesRegex(
            RuntimeError, "rollback"
        ), self.store.connection() as db:
            db.execute(
                "UPDATE combat_fights SET status='finished' WHERE id=%s", (fight.id,)
            )
            self.assertTrue(boss_score_runtime.finalize(db, fight)["eligible"])
            raise RuntimeError("rollback")
        with self.store.connection() as db:
            self.assertEqual(
                0,
                db.execute(
                    "SELECT count(*) AS n FROM boss_score_damage_receipts WHERE fight_id=%s",
                    (fight.id,),
                ).fetchone()["n"],
            )
            db.execute(
                "UPDATE combat_fights SET status='finished' WHERE id=%s", (fight.id,)
            )
            result = boss_score_runtime.finalize(db, fight)
            self.assertEqual(1000000, result["score"])
            self.assertTrue(result["eligible"])
            self.assertTrue(result["boss_defeated"])
            self.assertEqual(result, boss_score_runtime.finalize(db, fight))
            self.assertEqual(
                1,
                db.execute(
                    "SELECT count(*) AS n FROM boss_score_damage_receipts WHERE fight_id=%s",
                    (fight.id,),
                ).fetchone()["n"],
            )

    def test_forced_alive_win_and_early_ogrest_neo_kills_do_not_qualify(self):
        for reference, dead in ((5608, False), (4378, True), (5806, True)):
            with self.subTest(reference=reference):
                fight, _, _, _ = self.damage_fight(reference)
                fight.phase = "finished"
                fight.winner = 0
                if dead:
                    fight.actors[-1].hp = 0
                with self.store.connection() as db:
                    db.execute(
                        "UPDATE combat_fights SET status='finished' WHERE id=%s",
                        (fight.id,),
                    )
                    result = boss_score_runtime.finalize(db, fight)
                    self.assertFalse(result["eligible"])
                    self.assertEqual(0, result["score"])

    def test_early_defeat_flag_requires_a_real_boolean(self):
        with self.store.connection() as db:
            policy = db.execute(
                "SELECT value FROM settings WHERE name='boss_score_policy'"
            ).fetchone()["value"]
            policy["profiles"]["5608"]["allow_early_boss_defeat"] = "true"
            db.execute(
                "UPDATE settings SET value=%s WHERE name='boss_score_policy'",
                (Jsonb(policy),),
            )
        with self.assertRaisesRegex(ValueError, "early boss defeat flag"):
            self.encounter(5608)
