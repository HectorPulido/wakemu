"""Install the criterion supplement once beside the qualified resource/group set."""
from postgres_case import PostgresCase
from test_environmental_group_bulk_pipeline import RESOURCE_SEEDS, seed_sql


class EnvironmentalGroupCriteriaBulkTests(PostgresCase):
    def test_180_criterion_profiles_seal_beside_790_with_970_disabled_candidates(self):
        with self.store.connection() as db:
            for filename in RESOURCE_SEEDS:
                db.execute(seed_sql(filename), prepare=False)
            db.execute("UPDATE environmental_runtime_profiles SET sealed=true")
            db.execute(
                "UPDATE environmental_regional_schedule_policies SET sealed=true"
            )
            db.execute("SET CONSTRAINTS ALL IMMEDIATE")
            db.execute("SET CONSTRAINTS ALL DEFERRED")
            db.execute(seed_sql("environmental_group_profiles.sql"), prepare=False)
            db.execute("SET CONSTRAINTS ALL IMMEDIATE")
            before = {
                r["profile_key"]: dict(r)
                for r in db.execute(
                    "SELECT * FROM environmental_runtime_profiles ORDER BY profile_key"
                )
            }
            self.assertEqual(len(before), 790)
            db.execute("SET CONSTRAINTS ALL DEFERRED")
            db.execute(
                seed_sql("environmental_group_criteria_profiles.sql"), prepare=False
            )
            db.execute("SET CONSTRAINTS ALL IMMEDIATE")
            after = {
                r["profile_key"]: dict(r)
                for r in db.execute(
                    "SELECT * FROM environmental_runtime_profiles ORDER BY profile_key"
                )
            }
            self.assertEqual(len(after), 970)
            self.assertEqual({key: after[key] for key in before}, before)
            delta = set(after) - set(before)
            self.assertEqual(len(delta), 180)
            self.assertTrue(
                all(after[key]["sealed"] and not after[key]["enabled"] for key in delta)
            )
            rows = db.execute(
                "SELECT q.criterion_kind,r.mode,count(*) AS n "
                "FROM environmental_profile_location_policy q "
                "JOIN environmental_runtime_profiles r USING(profile_key,version) "
                "GROUP BY q.criterion_kind,r.mode"
            ).fetchall()
            self.assertEqual(
                {(r["criterion_kind"], r["mode"]): r["n"] for r in rows},
                {("all_wishes", "collaborative"): 95, ("neo_server", "solo"): 85},
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM environmental_regional_schedule_policies "
                    "WHERE version=6 AND sealed AND NOT enabled"
                ).fetchone()["n"],
                90,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM environmental_regional_schedule_candidates "
                    "WHERE version=6"
                ).fetchone()["n"],
                970,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM environmental_runtime_profiles "
                    "WHERE enabled OR NOT sealed"
                ).fetchone()["n"],
                0,
            )
            self.assertFalse(
                db.execute(
                    "SELECT enabled FROM environmental_random_roster_active WHERE singleton"
                ).fetchone()["enabled"]
            )
            # No dropped native variable or flattened multi-reward predicate
            # can hide behind a successful bulk count.
            mismatches = db.execute(
                """SELECT p.profile_key FROM environmental_profile_native_variable_policy p
                JOIN environmental_native_variables v ON v.source_key=p.source_key AND v.scenario_id=p.native_scenario_id
                LEFT JOIN environmental_profile_native_variable_bindings b ON b.profile_key=p.profile_key
                  AND b.version=p.version AND b.variable_index=v.ordinal AND b.native_name=v.native_name
                WHERE p.profile_key=ANY(%s) AND b.profile_key IS NULL""",
                (sorted(delta),),
            ).fetchall()
            self.assertEqual(mismatches, [])
            self.assertEqual(
                db.execute(
                    """SELECT count(*) AS n FROM environmental_profile_location_policy q
                JOIN environmental_runtime_profiles r USING(profile_key,version)
                WHERE NOT EXISTS(SELECT 1 FROM environmental_native_scenario_locations n
                 WHERE n.source_key=q.source_key AND n.scenario_id=q.native_scenario_id
                 AND n.protector_id=q.protector_id AND n.map_id=r.map_id AND n.region_id=r.region_id
                 AND n.native_criteria=q.native_criteria AND n.native_cells_present)"""
                ).fetchone()["n"],
                0,
            )
