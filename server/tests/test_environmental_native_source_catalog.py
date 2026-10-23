"""Bulk original environmental source import, authority boundaries and joins."""
import json
import os
from pathlib import Path

from postgres_case import PostgresCase


class EnvironmentalNativeSourceCatalogTests(PostgresCase):
    def setUp(self):
        super().setUp()
        root = Path(__file__).resolve().parents[2]
        migration = Path(
            os.environ.get(
                "WAKFU_ENVIRONMENTAL_SOURCE_MIGRATION",
                root / "server/migrations/275_environmental_native_source_catalog.sql",
            )
        )
        if not migration.is_file():
            self.skipTest("Original environmental source migration required")
        self.original = json.loads(
            (
                root
                / "agents_docs/reports/recurring-missions/ENVIRONMENTAL-SCENARIOS-INVENTORY-20261011.json"
            ).read_text()
        )
        with self.store.connection() as db:
            if (
                db.execute(
                    "SELECT to_regclass('environmental_native_scenarios') AS relation"
                ).fetchone()["relation"]
                is None
            ):
                db.execute(migration.read_text(), prepare=False)

    def test_complete_finite_native_import_preserves_order_raw_fields_and_inactive_boundary(
        self,
    ):
        with self.store.connection() as db:
            rows = db.execute("SELECT * FROM environmental_native_scenarios").fetchall()
            self.assertEqual(len(rows), 1208)
            self.assertEqual(sum(row["assigned"] for row in rows), 1191)
            self.assertFalse(any(row["activation_qualified"] for row in rows))
            self.assertEqual(
                {row["family"] for row in rows},
                {
                    "group_template",
                    "resource_interaction",
                    "destroy_monster_action",
                    "portal_boss_chain",
                },
            )
            objectives = db.execute(
                "SELECT count(*) AS total FROM environmental_native_objectives"
            ).fetchone()["total"]
            rewards = db.execute(
                "SELECT count(*) AS total FROM environmental_native_rewards_raw"
            ).fetchone()["total"]
            self.assertEqual((objectives, rewards), (10985, 1738))
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS total FROM environmental_native_group_members"
                ).fetchone()["total"],
                1509,
            )
            original_variables = [
                (row["id"], index, name)
                for row in self.original["scenarios"]
                for index, name in enumerate(row["variables"])
            ]
            actual_variables = db.execute(
                "SELECT scenario_id,ordinal,native_name FROM environmental_native_variables"
            ).fetchall()
            self.assertEqual(
                sorted(original_variables),
                sorted(
                    (row["scenario_id"], row["ordinal"], row["native_name"])
                    for row in actual_variables
                ),
            )
            original_configuration = {
                (row["id"], key, key.lower(), value)
                for row in self.original["scenarios"]
                for key, value in row["configuration"].items()
            }
            actual_configuration = db.execute(
                "SELECT scenario_id,native_key,normalized_key,native_value FROM environmental_native_configuration"
            ).fetchall()
            self.assertEqual(
                original_configuration,
                {
                    (
                        row["scenario_id"],
                        row["native_key"],
                        row["normalized_key"],
                        row["native_value"],
                    )
                    for row in actual_configuration
                },
            )
            raw = self.original["scenarios"][0]["rewards"][0]
            actual = db.execute(
                "SELECT * FROM environmental_native_rewards_raw WHERE scenario_id=%s AND reward_id=%s",
                (self.original["scenarios"][0]["id"], raw["id"]),
            ).fetchone()
            self.assertEqual(
                (actual["field_aai"], actual["field_ago"], actual["native_flag"]),
                (raw["field_aAi"], raw["field_agO"], raw["flag"]),
            )

    def test_catalog_cannot_enable_gameplay_or_mutate_original_authority(self):
        for statement in (
            "UPDATE environmental_native_scenarios SET activation_qualified=TRUE",
            "DELETE FROM environmental_native_group_members",
            "UPDATE environmental_native_rewards_raw SET field_aai=1",
        ):
            with self.subTest(statement=statement), self.assertRaisesRegex(
                Exception, "append-only"
            ):
                with self.store.connection() as db:
                    db.execute(statement)
        with self.assertRaises(Exception):
            with self.store.connection() as db:
                db.execute(
                    "INSERT INTO environmental_native_variables VALUES ('missing-source',-1,0,'invented')"
                )

    def test_original_reward_display_units_indices_and_native_rank_bound_never_authorize_grants(
        self,
    ):
        from psycopg.errors import CheckViolation
        from wakfu_server.objectives import environmental_runtime

        expected = []
        for scenario in self.original["scenarios"]:
            primary = sorted(
                (r for r in scenario["rewards"] if r["flag"]),
                key=lambda row: row["field_aHh"],
            )
            indices = {row["id"]: index for index, row in enumerate(primary)}
            for row in scenario["rewards"]:
                expected.append(
                    (
                        scenario["id"],
                        row["id"],
                        row["field_aAi"],
                        row["field_aHj"],
                        row["field_agO"],
                        row["field_aHk"],
                        row["field_aHh"],
                        row["flag"],
                        indices.get(row["id"]),
                        False,
                    )
                )
        with self.store.connection() as db:
            rows = db.execute(
                "SELECT scenario_id,reward_id,item_reference,item_quantity,base_xp,kamas,display_order,"
                "primary_reward_list,primary_result_index,server_grant_authorized FROM environmental_native_reward_display"
            ).fetchall()
            actual = [tuple(row.values()) for row in rows]
            self.assertEqual(sorted(actual), sorted(expected))
            self.assertEqual(len(actual), 1738)
            self.assertEqual(sum(row["item_reference"] > 0 for row in rows), 1506)
            self.assertEqual(sum(row["base_xp"] > 0 for row in rows), 1586)
            self.assertTrue(
                all(
                    row["kamas"] == 0 and not row["server_grant_authorized"]
                    for row in rows
                )
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM environmental_runtime_profiles"
                ).fetchone()["n"],
                0,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM environmental_reward_entitlements"
                ).fetchone()["n"],
                0,
            )
            db.execute(
                "INSERT INTO environmental_runtime_profiles "
                "(profile_key,version,family,mode,map_id,region_id,duration_ms,anchor_ms,level_min,level_max,authority,source_sha256,catalog_revision) "
                "VALUES('rank-bound',1,'resource_collect','race',1,1,1000,0,1,2,'test-only',%s,%s)",
                ("0" * 64, "1" * 64),
            )
            with self.assertRaises(CheckViolation), db.transaction():
                db.execute(
                    "INSERT INTO environmental_profile_evaluation VALUES('rank-bound',1,'first_completion',32768,'commit_order','test-only')"
                )
        policy = dict(
            evaluator="first_completion",
            winner_count=32767,
            tie_policy="commit_order",
            source_authority="test-only",
        )
        self.assertIs(environmental_runtime.validate_evaluation("race", policy), policy)
        with self.assertRaisesRegex(ValueError, "native display"):
            environmental_runtime.validate_evaluation(
                "race", dict(policy, winner_count=32768)
            )
