"""One real SQL installation of all frozen environmental resource/group profiles."""
from pathlib import Path

from postgres_case import PostgresCase


SEEDS = Path(__file__).parents[1] / "seeds"
RESOURCE_SEEDS = (
    "environmental_resource_profiles.sql",
    "environmental_resource_races.sql",
    "environmental_resource_competitions.sql",
    "environmental_resource_results.sql",
    "environmental_resource_level_criteria.sql",
)


def seed_sql(filename):
    # Keep all row guards/deferred validation; caller owns one SQL transaction.
    return (
        (SEEDS / filename)
        .read_text()
        .replace("\nBEGIN;\n", "\n")
        .replace("\nCOMMIT;\n", "\n")
    )


class EnvironmentalGroupBulkPipelineTests(PostgresCase):
    def test_all_790_profiles_and_candidates_seal_with_438_exact_group_sources_and_native_ui(
        self,
    ):
        with self.store.connection() as db:
            for filename in RESOURCE_SEEDS:
                db.execute(seed_sql(filename), prepare=False)
            # Resource seeds intentionally leave authority review/sealing to
            # the installer. Seal their existing exact rows before the group
            # supplement installs a combined immutable schedule version.
            db.execute("UPDATE environmental_runtime_profiles SET sealed=true")
            db.execute(
                "UPDATE environmental_regional_schedule_policies SET sealed=true"
            )
            db.execute("SET CONSTRAINTS ALL IMMEDIATE")
            db.execute("SET CONSTRAINTS ALL DEFERRED")
            db.execute(seed_sql("environmental_group_profiles.sql"), prepare=False)
            db.execute("UPDATE environmental_runtime_profiles SET sealed=true")
            db.execute(
                "UPDATE environmental_regional_schedule_policies SET sealed=true"
            )
            db.execute("SET CONSTRAINTS ALL IMMEDIATE")
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM environmental_runtime_profiles"
                ).fetchone()["n"],
                790,
            )
            groups = db.execute(
                "SELECT mode,count(*) AS n FROM environmental_runtime_profiles "
                "WHERE profile_key LIKE 'group-native-%' GROUP BY mode"
            ).fetchall()
            self.assertEqual(
                {r["mode"]: r["n"] for r in groups},
                dict(solo=90, race=90, competitive=90, collaborative=168),
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(DISTINCT native_scenario_id) AS n FROM environmental_runtime_profiles "
                    "WHERE profile_key LIKE 'group-native-%'"
                ).fetchone()["n"],
                391,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM environmental_regional_schedule_policies "
                    "WHERE version=5 AND sealed AND NOT enabled"
                ).fetchone()["n"],
                90,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM environmental_regional_schedule_candidates "
                    "WHERE version=5"
                ).fetchone()["n"],
                790,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM environmental_profile_native_variable_bindings "
                    "WHERE profile_key LIKE 'group-native-%'"
                ).fetchone()["n"],
                5670,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM environmental_profile_simple_result_policy "
                    "WHERE profile_key LIKE 'group-native-%'"
                ).fetchone()["n"],
                258,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM environmental_profile_ranked_reward_policy "
                    "WHERE profile_key LIKE 'group-native-%'"
                ).fetchone()["n"],
                180,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM environmental_profile_ranked_reward_bands "
                    "WHERE profile_key LIKE 'group-native-%'"
                ).fetchone()["n"],
                360,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM environmental_runtime_profiles WHERE enabled OR NOT sealed"
                ).fetchone()["n"],
                0,
            )
            self.assertFalse(
                db.execute(
                    "SELECT enabled FROM environmental_random_roster_active WHERE singleton"
                ).fetchone()["enabled"]
            )
            # Every published variable slot is the full original array; all
            # secondary projections were checked by SQL sealing above.
            mismatches = db.execute(
                """SELECT p.profile_key FROM environmental_profile_native_variable_policy p
                JOIN environmental_native_variables v ON v.source_key=p.source_key AND v.scenario_id=p.native_scenario_id
                LEFT JOIN environmental_profile_native_variable_bindings b ON b.profile_key=p.profile_key
                  AND b.version=p.version AND b.variable_index=v.ordinal AND b.native_name=v.native_name
                WHERE p.profile_key LIKE 'group-native-%' AND b.profile_key IS NULL"""
            ).fetchall()
            self.assertEqual(mismatches, [])
