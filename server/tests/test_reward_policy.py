import hashlib
import json
from pathlib import Path

from postgres_case import PostgresCase
from psycopg.errors import CheckViolation

from wakfu_server.reward_policy import kamas_amount, resolve, xp_amount


def context(
    character_id, *, level=1, wisdom=0, winners=None, losers=None, challenge=0, star=0
):
    return {
        "winner_team": 0,
        "winners": winners
        or [
            {
                "level": level,
                "player": True,
                "eligible": True,
                "character_id": character_id,
                "wisdom": wisdom,
            }
        ],
        "losers": losers or [{"level": 1, "monster_reference": 500}],
        "challenge_percent": challenge,
        "star_percent": star,
    }


class RewardPolicyMathTests(PostgresCase):
    def test_dofus_reference_golden_xp_vectors_preserve_integer_casts(self):
        one = context(7)
        self.assertEqual(
            xp_amount(
                character_id=7,
                context=one,
                group_xp=1000,
                xp_rate_bp=10000,
                conquest_rate_bp=10000,
            ),
            1105,
        )
        self.assertEqual(
            xp_amount(
                character_id=7,
                context=context(7, challenge=99, star=99),
                group_xp=1000,
                xp_rate_bp=10000,
                conquest_rate_bp=10000,
            ),
            1105,
        )
        self.assertEqual(
            xp_amount(
                character_id=7,
                context=context(7, challenge=100, star=100),
                group_xp=1000,
                xp_rate_bp=10000,
                conquest_rate_bp=10000,
            ),
            4422,
        )

    def test_group_split_truncates_before_float_formula(self):
        ctx = context(
            7,
            winners=[
                {
                    "level": 1,
                    "player": True,
                    "eligible": True,
                    "character_id": 7,
                    "wisdom": 0,
                },
                {
                    "level": 1,
                    "player": True,
                    "eligible": True,
                    "character_id": 8,
                    "wisdom": 0,
                },
            ],
        )
        self.assertEqual(
            xp_amount(
                character_id=7,
                context=ctx,
                group_xp=1001,
                xp_rate_bp=10000,
                conquest_rate_bp=10000,
            ),
            1306,
        )

    def test_single_player_ratio_and_dofus_larva_reference_vector(self):
        self.assertEqual(
            xp_amount(
                character_id=7,
                context=context(7, losers=[{"level": 2, "monster_reference": 500}]),
                group_xp=200,
                xp_rate_bp=10000,
                conquest_rate_bp=10000,
            ),
            221,
        )

    def test_configured_xp_rate_applies_at_198_199_and_200_without_dofus_exception(
        self,
    ):
        for level in (198, 199, 200):
            ctx = context(
                7, level=level, losers=[{"level": 1, "monster_reference": 500}]
            )
            base = xp_amount(
                character_id=7,
                context=ctx,
                group_xp=100000,
                xp_rate_bp=10000,
                conquest_rate_bp=10000,
            )
            doubled = xp_amount(
                character_id=7,
                context=ctx,
                group_xp=100000,
                xp_rate_bp=20000,
                conquest_rate_bp=10000,
            )
            self.assertGreater(doubled, base)
            self.assertIn(doubled, (base * 2, base * 2 + 1))

    def test_group_size_is_eligible_players_capped_at_eight(self):
        winners = [
            {
                "level": 30,
                "player": True,
                "eligible": True,
                "character_id": n,
                "wisdom": 0,
            }
            for n in range(1, 10)
        ]
        ctx = context(
            1, winners=winners, losers=[{"level": 200, "monster_reference": 500}]
        )
        capped = xp_amount(
            character_id=1,
            context=ctx,
            group_xp=8000,
            xp_rate_bp=10000,
            conquest_rate_bp=10000,
        )
        self.assertGreater(capped, 0)
        excluded = [dict(row, eligible=False) for row in winners]
        ctx = context(
            1, winners=excluded, losers=[{"level": 200, "monster_reference": 500}]
        )
        self.assertEqual(
            xp_amount(
                character_id=1,
                context=ctx,
                group_xp=8000,
                xp_rate_bp=10000,
                conquest_rate_bp=10000,
            ),
            0,
        )

    def test_invalid_context_types_and_missing_recipient_fail_closed(self):
        bad = context(7)
        bad["winners"][0]["eligible"] = 1
        with self.assertRaises(ValueError):
            xp_amount(
                character_id=7,
                context=bad,
                group_xp=1000,
                xp_rate_bp=10000,
                conquest_rate_bp=10000,
            )
        bad = context(7)
        bad["winners"][0]["wisdom"] = True
        with self.assertRaises(ValueError):
            xp_amount(
                character_id=7,
                context=bad,
                group_xp=1000,
                xp_rate_bp=10000,
                conquest_rate_bp=10000,
            )
        for wisdom in (-501, 201):
            bad = context(7)
            bad["winners"][0]["wisdom"] = wisdom
            with self.assertRaises(ValueError):
                xp_amount(
                    character_id=7,
                    context=bad,
                    group_xp=1000,
                    xp_rate_bp=10000,
                    conquest_rate_bp=10000,
                )
        modest_negative = xp_amount(
            character_id=7,
            context=context(7, wisdom=-5),
            group_xp=1000,
            xp_rate_bp=10000,
            conquest_rate_bp=10000,
        )
        self.assertLess(modest_negative, 1105)
        self.assertEqual(
            xp_amount(
                character_id=7,
                context=context(7, wisdom=-500),
                group_xp=1000,
                xp_rate_bp=10000,
                conquest_rate_bp=10000,
            ),
            0,
        )
        bad = context(8)
        with self.assertRaises(ValueError):
            xp_amount(
                character_id=7,
                context=bad,
                group_xp=1000,
                xp_rate_bp=10000,
                conquest_rate_bp=10000,
            )

    def test_kamas_uses_named_inclusive_bounds_and_java_rounding(self):
        self.assertEqual(
            kamas_amount(minimum=10, maximum=20, kamas_rate_bp=10000, roll_index=0),
            (10, 0),
        )
        self.assertEqual(
            kamas_amount(minimum=10, maximum=20, kamas_rate_bp=10000, roll_index=10),
            (20, 10),
        )
        self.assertEqual(
            kamas_amount(minimum=10, maximum=10, kamas_rate_bp=10000, roll_index=0),
            (10, 0),
        )
        self.assertEqual(
            kamas_amount(minimum=11, maximum=11, kamas_rate_bp=5000, roll_index=0),
            (6, 0),
        )
        with self.assertRaises(ValueError):
            kamas_amount(minimum=20, maximum=10, kamas_rate_bp=10000, roll_index=0)
        with self.assertRaises(ValueError):
            kamas_amount(minimum=1, maximum=2, kamas_rate_bp=10000, roll_index=True)


class RewardPolicyPostgresTests(PostgresCase):
    def setUp(self):
        super().setUp()
        self.store.clock = lambda: 1000
        self.account_id = self.store.register("reward-policy", "local-password")["id"]
        self.character = self.store.create_character(self.account_id, "RewardPolicy")
        self.generation = self.store.begin_session(self.account_id)
        self.store.select_character(
            self.account_id, self.generation, self.character["id"]
        )
        with self.store.connection() as db:
            self.fight_id = db.execute(
                "INSERT INTO combat_fights(status) VALUES('finished') RETURNING id"
            ).fetchone()["id"]
            db.execute(
                "INSERT INTO combat_fight_participants(fight_id,character_id,account_id,team) VALUES(%s,%s,%s,0)",
                (self.fight_id, self.character["id"], self.account_id),
            )
            db.execute(
                "INSERT INTO combat_reward_monster_levels(monster_reference,monster_level,base_xp,min_kamas,max_kamas,source) VALUES(500,1,1000,10,20,'test fixture')"
            )
        self.ctx = context(self.character["id"])

    def test_resolve_persists_policy_hash_and_replays_after_config_and_catalog_change(
        self,
    ):
        with self.store.connection() as db:
            first = resolve(
                self.store,
                db,
                account_id=self.account_id,
                generation=self.generation,
                character_id=self.character["id"],
                fight_id=self.fight_id,
                context=self.ctx,
                kamas_roll_index=10,
            )
            self.assertEqual((first.policy.xp, first.policy.kamas), (1105, 20))
            self.assertFalse(first.replayed)
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO combat_reward_policy_versions(version,xp_rate_bp,kamas_rate_bp,conquest_rate_bp) VALUES(2,20000,0,10000)"
            )
            db.execute(
                "UPDATE combat_reward_policy_active SET version=2 WHERE singleton=true"
            )
            db.execute(
                "UPDATE combat_reward_monster_levels SET base_xp=9000,min_kamas=30,max_kamas=40 WHERE monster_reference=500 AND monster_level=1"
            )
        with self.store.connection() as db:
            replay = resolve(
                self.store,
                db,
                account_id=self.account_id,
                generation=self.generation,
                character_id=self.character["id"],
                fight_id=self.fight_id,
                context=self.ctx,
                kamas_roll_index=0,
            )
            self.assertEqual((replay.policy.xp, replay.policy.kamas), (1105, 20))
            self.assertEqual(replay.version, 1)
            self.assertTrue(replay.replayed)
            self.assertEqual(replay.snapshot_sha256, first.snapshot_sha256)
            rows = db.execute(
                "SELECT count(*) AS n FROM fight_reward_policy_receipts WHERE fight_id=%s AND character_id=%s",
                (self.fight_id, self.character["id"]),
            ).fetchone()
            self.assertEqual(rows["n"], 1)

    def test_missing_wakfu_catalog_row_fails_without_partial_receipt(self):
        with self.store.connection() as db:
            db.execute(
                "DELETE FROM combat_reward_monster_levels WHERE monster_reference=500"
            )
            db.execute("DELETE FROM combat_reward_level_defaults WHERE monster_level=1")
        with self.assertRaisesRegex(ValueError, "Missing configured reward data"):
            with self.store.connection() as db:
                resolve(
                    self.store,
                    db,
                    account_id=self.account_id,
                    generation=self.generation,
                    character_id=self.character["id"],
                    fight_id=self.fight_id,
                    context=self.ctx,
                    kamas_roll_index=0,
                )
        with self.store.connection() as db:
            self.assertIsNone(
                db.execute("SELECT 1 FROM fight_reward_policy_receipts").fetchone()
            )

    def test_level_default_is_used_without_cross_game_reference_mapping(self):
        with self.store.connection() as db:
            db.execute(
                "DELETE FROM combat_reward_monster_levels WHERE monster_reference=500"
            )
            db.execute(
                "INSERT INTO combat_reward_level_defaults(monster_level,base_xp,min_kamas,max_kamas,source) "
                "VALUES(1,1000,10,20,'local Dofus-derived level policy') "
                "ON CONFLICT(monster_level) DO UPDATE SET base_xp=EXCLUDED.base_xp, "
                "min_kamas=EXCLUDED.min_kamas,max_kamas=EXCLUDED.max_kamas,source=EXCLUDED.source"
            )
        with self.store.connection() as db:
            decision = resolve(
                self.store,
                db,
                account_id=self.account_id,
                generation=self.generation,
                character_id=self.character["id"],
                fight_id=self.fight_id,
                context=self.ctx,
                kamas_roll_index=0,
            )
        self.assertEqual((decision.policy.xp, decision.policy.kamas), (1105, 10))
        self.assertEqual(
            decision.snapshot["monster_catalog"][0]["source_kind"], "level_default"
        )

    def test_reference_override_wins_over_level_default(self):
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO combat_reward_level_defaults(monster_level,base_xp,min_kamas,max_kamas,source) "
                "VALUES(1,2000,100,200,'local Dofus-derived level policy') "
                "ON CONFLICT(monster_level) DO UPDATE SET base_xp=EXCLUDED.base_xp, "
                "min_kamas=EXCLUDED.min_kamas,max_kamas=EXCLUDED.max_kamas,source=EXCLUDED.source"
            )
        with self.store.connection() as db:
            decision = resolve(
                self.store,
                db,
                account_id=self.account_id,
                generation=self.generation,
                character_id=self.character["id"],
                fight_id=self.fight_id,
                context=self.ctx,
                kamas_roll_index=0,
            )
        self.assertEqual((decision.policy.xp, decision.policy.kamas), (1105, 10))
        self.assertEqual(
            decision.snapshot["monster_catalog"][0]["source_kind"], "reference_override"
        )

    def test_active_sql_rates_change_the_next_fight_only(self):
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO combat_reward_policy_versions(version,xp_rate_bp,kamas_rate_bp,conquest_rate_bp) VALUES(2,20000,0,10000)"
            )
            db.execute(
                "UPDATE combat_reward_policy_active SET version=2 WHERE singleton=true"
            )
            new_fight_id = db.execute(
                "INSERT INTO combat_fights(status) VALUES('finished') RETURNING id"
            ).fetchone()["id"]
            db.execute(
                "INSERT INTO combat_fight_participants(fight_id,character_id,account_id,team) VALUES(%s,%s,%s,0)",
                (new_fight_id, self.character["id"], self.account_id),
            )
        with self.store.connection() as db:
            next_decision = resolve(
                self.store,
                db,
                account_id=self.account_id,
                generation=self.generation,
                character_id=self.character["id"],
                fight_id=new_fight_id,
                context=self.ctx,
                kamas_roll_index=0,
            )
        self.assertEqual(next_decision.version, 2)
        self.assertEqual(
            (next_decision.policy.xp, next_decision.policy.kamas), (2211, 0)
        )

    def test_stale_lease_and_nonfinished_or_nonwinning_participant_rejected(self):
        old_generation = self.generation
        self.generation = self.store.begin_session(self.account_id)
        self.store.select_character(
            self.account_id, self.generation, self.character["id"]
        )
        with self.assertRaises(ValueError):
            with self.store.connection() as db:
                resolve(
                    self.store,
                    db,
                    account_id=self.account_id,
                    generation=old_generation,
                    character_id=self.character["id"],
                    fight_id=self.fight_id,
                    context=self.ctx,
                )
        with self.store.connection() as db:
            db.execute(
                "UPDATE combat_fights SET status='active' WHERE id=%s", (self.fight_id,)
            )
        with self.assertRaisesRegex(ValueError, "finished winning"):
            with self.store.connection() as db:
                resolve(
                    self.store,
                    db,
                    account_id=self.account_id,
                    generation=self.generation,
                    character_id=self.character["id"],
                    fight_id=self.fight_id,
                    context=self.ctx,
                )

    def test_injected_caller_rollback_removes_policy_snapshot(self):
        with self.assertRaises(RuntimeError):
            with self.store.connection() as db:
                decision = resolve(
                    self.store,
                    db,
                    account_id=self.account_id,
                    generation=self.generation,
                    character_id=self.character["id"],
                    fight_id=self.fight_id,
                    context=self.ctx,
                    kamas_roll_index=5,
                )
                self.assertEqual(decision.policy.xp, 1105)
                raise RuntimeError("injected later reward failure")
        with self.store.connection() as db:
            self.assertIsNone(
                db.execute("SELECT 1 FROM fight_reward_policy_receipts").fetchone()
            )

    def test_policy_and_existing_reward_receipt_share_the_callers_transaction(self):
        from wakfu_server.combat_rewards import award
        from wakfu_server.combat_state import Actor, Fight

        fight = Fight(
            self.fight_id,
            [
                Actor(
                    self.character["id"],
                    0,
                    (0, 0, 0),
                    60,
                    6,
                    3,
                    100,
                    1,
                    self.account_id,
                    True,
                ),
                Actor(-500, 1, (1, 0, 0), 12, 4, 2, 10, 1),
            ],
            [(0, 0, 0), (1, 0, 0)],
            {0: {(0, 0, 0)}, 1: {(1, 0, 0)}},
        )
        fight.phase, fight.winner = "finished", 0
        before = self.store.character(self.account_id, self.character["id"])
        with self.assertRaises(RuntimeError):
            with self.store.connection() as db:
                decision = resolve(
                    self.store,
                    db,
                    account_id=self.account_id,
                    generation=self.generation,
                    character_id=self.character["id"],
                    fight_id=self.fight_id,
                    context=self.ctx,
                    kamas_roll_index=0,
                )
                award(
                    self.store,
                    self.account_id,
                    self.generation,
                    self.character["id"],
                    fight,
                    decision.policy,
                    db=db,
                )
                raise RuntimeError("injected failure after reward persistence")
        after_rollback = self.store.character(self.account_id, self.character["id"])
        self.assertEqual(after_rollback["xp"], before["xp"])
        with self.store.connection() as db:
            self.assertIsNone(
                db.execute("SELECT 1 FROM fight_reward_policy_receipts").fetchone()
            )
            self.assertIsNone(db.execute("SELECT 1 FROM fight_rewards").fetchone())

        with self.store.connection() as db:
            decision = resolve(
                self.store,
                db,
                account_id=self.account_id,
                generation=self.generation,
                character_id=self.character["id"],
                fight_id=self.fight_id,
                context=self.ctx,
                kamas_roll_index=0,
            )
            result = award(
                self.store,
                self.account_id,
                self.generation,
                self.character["id"],
                fight,
                decision.policy,
                db=db,
            )
            self.assertTrue(result["awarded"])
            self.assertEqual(result["xp"], decision.policy.xp)
            self.assertEqual(result["kamas"], decision.policy.kamas)
        with self.store.connection() as db:
            self.assertIsNotNone(
                db.execute("SELECT 1 FROM fight_reward_policy_receipts").fetchone()
            )
            self.assertIsNotNone(db.execute("SELECT 1 FROM fight_rewards").fetchone())

    def test_negative_wisdom_clamp_is_audited_and_combat_finish_commits(self):
        from wakfu_server.combat_lifecycle import prepare_finish
        from wakfu_server.combat_reward_context import resolve_policy
        from wakfu_server.combat_runtime_messages import RuntimeMessages
        from wakfu_server.combat_state import Actor, Fight
        from wakfu_server.monsters import owned_instance

        with self.store.connection() as db:
            db.execute(
                "UPDATE combat_fights SET status='active' WHERE id=%s", (self.fight_id,)
            )
        character = self.store.character(self.account_id, self.character["id"])
        monster = owned_instance(5525, 1, -550, map_id=1134, x=1, y=0, z=0)
        player = Actor(
            character["id"],
            0,
            (0, 0, 0),
            character["hp"],
            6,
            3,
            100,
            character["level"],
            self.account_id,
            True,
            max_hp=character["max_hp"],
        )
        player.effect_stats = {36: -500}
        enemy = Actor(
            monster["id"],
            1,
            (1, 0, 0),
            monster["hp"],
            monster["ap"],
            monster["mp"],
            monster["initiative"],
            monster["level"],
        )
        fight = Fight(
            self.fight_id,
            [player, enemy],
            [(0, 0, 0), (1, 0, 0)],
            {0: {(0, 0, 0)}, 1: {(1, 0, 0)}},
        )
        fight.ready(self.account_id)
        fight.apply_damage(player.id, enemy.id, enemy.hp)
        self.assertEqual((fight.phase, fight.winner), ("finished", 0))
        runtime = RuntimeMessages(fight)
        metadata = {
            player.id: {
                "kind": "player",
                "account_id": self.account_id,
                "name": character["name"],
                "breed": character["breed"],
                "is_male": True,
            },
            enemy.id: {"kind": "monster", "ref": monster["ref"]},
        }
        completed = prepare_finish(
            self.store,
            self.account_id,
            self.generation,
            character,
            runtime,
            metadata,
            duration_ms=1000,
            fight_instance_id=self.fight_id,
            policy_resolver=lambda db: resolve_policy(
                self.store,
                db,
                account_id=self.account_id,
                generation=self.generation,
                character=character,
                fight=fight,
                monsters=[monster],
            ),
        )
        self.assertTrue(completed["reward"]["awarded"])
        self.assertEqual(completed["reward"]["xp"], 0)
        with self.store.connection() as db:
            receipt = db.execute(
                "SELECT xp,snapshot FROM fight_reward_policy_receipts WHERE fight_id=%s AND character_id=%s",
                (self.fight_id, self.character["id"]),
            ).fetchone()
            self.assertEqual(receipt["xp"], 0)
            self.assertTrue(receipt["snapshot"]["negative_formula_clamped"])
            self.assertEqual(
                db.execute(
                    "SELECT status FROM combat_fights WHERE id=%s", (self.fight_id,)
                ).fetchone()["status"],
                "finished",
            )

    def test_policy_and_catalog_constraints_reject_invalid_values(self):
        with self.assertRaises(CheckViolation):
            with self.store.connection() as db:
                db.execute(
                    "INSERT INTO combat_reward_policy_versions(version,xp_rate_bp,kamas_rate_bp,conquest_rate_bp) VALUES(2,-1,10000,10000)"
                )
        with self.assertRaises(CheckViolation):
            with self.store.connection() as db:
                db.execute(
                    "INSERT INTO combat_reward_monster_levels(monster_reference,monster_level,base_xp,min_kamas,max_kamas,source) VALUES(501,1,10,20,10,'invalid fixture')"
                )

    def test_migration_defaults_match_the_hashed_dofus_level_export(self):
        path = (
            Path(__file__).resolve().parents[1]
            / "protocol"
            / "dofus-reward-level-reference.json"
        )
        raw = path.read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        data = json.loads(raw)
        expected = data["defaults_by_level"]
        self.assertEqual(len(expected), 200)
        with self.store.connection() as db:
            actual = db.execute(
                "SELECT monster_level,base_xp,min_kamas,max_kamas,source "
                "FROM combat_reward_level_defaults ORDER BY monster_level"
            ).fetchall()
        self.assertEqual(len(actual), 200)
        for row, expected_row in zip(actual, expected):
            self.assertEqual(
                (
                    row["monster_level"],
                    row["base_xp"],
                    row["min_kamas"],
                    row["max_kamas"],
                ),
                (
                    expected_row["level"],
                    expected_row["base_xp"],
                    expected_row["min_kamas"],
                    expected_row["max_kamas"],
                ),
            )
            self.assertIn(f"dofus-level-json-sha256:{digest}", row["source"])
            self.assertIn(f"source_level:{expected_row['source_level']}", row["source"])


if __name__ == "__main__":
    import unittest

    unittest.main()
