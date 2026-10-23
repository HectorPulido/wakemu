"""Explicit profile-bound race/competition ranking, not native policy invention."""
from dataclasses import replace
import unittest

from wakfu_server.objectives import environmental_runtime as rules
from test_environmental_durable_lifecycle import EnvironmentalDurableLifecycleTests


class EnvironmentalRankingPolicyTests(unittest.TestCase):
    def test_explicit_ties_are_deterministic_and_unknown_evaluators_fail_closed(self):
        rows = [
            dict(character_id=9, score=4),
            dict(character_id=3, score=4),
            dict(character_id=1, score=2),
        ]
        policy = dict(
            evaluator="score_at_deadline",
            winner_count=1,
            tie_policy="share_boundary",
            source_authority="test-only",
        )
        ranked = rules.competitive_order(rows, policy)
        self.assertEqual(
            [(r["character_id"], r["display_rank"], r["rewarded"]) for r in ranked],
            [(3, 1, True), (9, 1, True), (1, 3, False)],
        )
        ranked = rules.competitive_order(rows, dict(policy, tie_policy="character_id"))
        self.assertEqual(
            [(r["character_id"], r["display_rank"], r["rewarded"]) for r in ranked],
            [(3, 1, True), (9, 2, False), (1, 3, False)],
        )
        for change in (
            dict(evaluator="unknown"),
            dict(tie_policy="assume-native"),
            dict(winner_count=True),
            dict(source_authority=""),
        ):
            with self.subTest(change=change), self.assertRaises(ValueError):
                rules.competitive_order(rows, dict(policy, **change))
        self.assertEqual(rules.competitive_order([], policy), ())


class EnvironmentalRankingPostgresTests(EnvironmentalDurableLifecycleTests):
    def ranked_profile(self, mode, *, winners=1, ties=None):
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO environmental_runtime_profiles "
                "(profile_key,version,family,mode,map_id,region_id,duration_ms,anchor_ms,level_min,level_max,"
                "authority,source_sha256,catalog_revision) "
                "VALUES('test-policy',1,'resource_collect',%s,527,17,60000,%s,1,245,'test-only',%s,%s)",
                (mode, self.now_ms - 1000, "0" * 64, "1" * 64),
            )
            db.execute(
                "INSERT INTO environmental_profile_evaluation VALUES('test-policy',1,%s,%s,%s,'test-only')",
                (
                    "first_completion" if mode == "race" else "score_at_deadline",
                    winners,
                    ties or ("commit_order" if mode == "race" else "share_boundary"),
                ),
            )
            db.execute(
                "INSERT INTO environmental_profile_objectives VALUES('test-policy',1,'collect','resource_collect',1337,3,1,'quantity',2)"
            )
            db.execute(
                "INSERT INTO environmental_profile_rewards VALUES('test-policy',1,0,'xp',NULL,100,'test-only')"
            )
            db.execute(
                "UPDATE environmental_runtime_profiles SET sealed=true,enabled=true WHERE profile_key='test-policy'"
            )

    def test_race_uses_serialized_finish_order_and_exact_winner_count(self):
        other, lease, second = self.owner()
        self.ranked_profile("race", winners=2)
        event = self.admit()["instances"][0]["instance_id"]
        self.admit(other, lease, second)
        self.roster(event, [801, 802, 803])
        self.consume(replace(self.fact(801), quantity=2))
        self.consume(
            replace(self.fact(802, account=other, character=second), quantity=2)
        )
        self.assertEqual(self.consume(replace(self.fact(803), quantity=2)), ())
        with self.store.connection() as db:
            ranked = db.execute(
                "SELECT * FROM environmental_event_rankings ORDER BY position"
            ).fetchall()
            self.assertEqual(
                [(r["character_id"], r["position"], r["rewarded"]) for r in ranked],
                [(self.character["id"], 1, True), (second["id"], 2, True)],
            )
            self.assertEqual(
                db.execute(
                    "SELECT state FROM environmental_event_instances"
                ).fetchone()["state"],
                "completed",
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM environmental_reward_entitlements"
                ).fetchone()["n"],
                2,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM environmental_cleanup_outbox"
                ).fetchone()["n"],
                3,
            )
        self.assertEqual(len(self.admit()["rewards"]["delivered"]), 1)
        self.assertEqual(
            len(self.admit(other, lease, second)["rewards"]["delivered"]), 1
        )
        self.assertEqual(self.admit()["rewards"]["delivered"], [])

    def test_competition_waits_for_deadline_keeps_full_score_and_shares_boundary_ties(
        self,
    ):
        other, lease, second = self.owner()
        third_account, third_lease, third = self.owner()
        idle_account, idle_lease, idle = self.owner()
        self.ranked_profile("competitive")
        event = self.admit()["instances"][0]["instance_id"]
        for account, generation, character in (
            (other, lease, second),
            (third_account, third_lease, third),
            (idle_account, idle_lease, idle),
        ):
            self.admit(account, generation, character)
        self.roster(event, [901, 902, 903, 904])
        self.consume(replace(self.fact(901), quantity=4))
        self.consume(
            replace(self.fact(902, account=other, character=second), quantity=4)
        )
        self.consume(
            replace(self.fact(903, account=third_account, character=third), quantity=2)
        )
        self.assertEqual(self.consume(replace(self.fact(901), quantity=4)), ())
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM environmental_reward_entitlements"
                ).fetchone()["n"],
                0,
            )
            self.assertEqual(
                db.execute(
                    "SELECT sum(quantity) AS n FROM environmental_progress"
                ).fetchone()["n"],
                10,
            )
        completed = self.admit(now_ms=self.now_ms + 60000)
        self.assertEqual(len(completed["rewards"]["delivered"]), 1)
        self.assertEqual(
            self.consume(
                replace(self.fact(904), quantity=99, occurred_at_ms=self.now_ms + 60000)
            ),
            (),
        )
        with self.store.connection() as db:
            ranked = db.execute(
                "SELECT * FROM environmental_event_rankings ORDER BY position"
            ).fetchall()
            self.assertEqual(
                [(r["score"], r["display_rank"], r["rewarded"]) for r in ranked],
                [(4, 1, True), (4, 1, True), (2, 3, False)],
            )
            self.assertEqual(
                {r["character_id"] for r in ranked if r["rewarded"]},
                {self.character["id"], second["id"]},
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM environmental_reward_entitlements"
                ).fetchone()["n"],
                2,
            )
        self.assertEqual(
            len(
                self.admit(other, lease, second, now_ms=self.now_ms + 60001)["rewards"][
                    "delivered"
                ]
            ),
            1,
        )
        self.assertEqual(
            self.admit(third_account, third_lease, third, now_ms=self.now_ms + 60002)[
                "rewards"
            ]["delivered"],
            [],
        )
        self.assertEqual(
            self.admit(now_ms=self.now_ms + 60003)["rewards"]["delivered"], []
        )
        with self.assertRaisesRegex(Exception, "immutable"):
            with self.store.connection() as db:
                db.execute("UPDATE environmental_profile_evaluation SET winner_count=3")
