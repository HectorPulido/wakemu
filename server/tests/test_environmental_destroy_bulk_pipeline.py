"""One additive SQL installation of exact native-action destruction profiles."""
from postgres_case import PostgresCase
from test_environmental_group_bulk_pipeline import RESOURCE_SEEDS, seed_sql


class EnvironmentalDestroyBulkPipelineTests(PostgresCase):
    def test_twelve_destroy_profiles_seal_beside_970_with_982_disabled_candidates(self):
        self.qualify_corpus(named=False)

    def test_280_named_destroy_profiles_preserve_982_and_seal_1262_disabled_candidates(
        self,
    ):
        self.qualify_corpus(named=True)

    def qualify_corpus(self, *, named):
        with self.store.connection() as db:
            sizing = [
                dict(r)
                for r in db.execute(
                    "SELECT * FROM environmental_random_roster_versions ORDER BY policy_version"
                )
            ]
            active = dict(
                db.execute(
                    "SELECT * FROM environmental_random_roster_active WHERE singleton"
                ).fetchone()
            )
            for filename in RESOURCE_SEEDS:
                db.execute(seed_sql(filename), prepare=False)
            db.execute("UPDATE environmental_runtime_profiles SET sealed=true")
            db.execute(
                "UPDATE environmental_regional_schedule_policies SET sealed=true"
            )
            db.execute("SET CONSTRAINTS ALL IMMEDIATE")
            db.execute("SET CONSTRAINTS ALL DEFERRED")
            db.execute(seed_sql("environmental_group_profiles.sql"), prepare=False)
            db.execute("SET CONSTRAINTS ALL DEFERRED")
            db.execute(
                seed_sql("environmental_group_criteria_profiles.sql"), prepare=False
            )
            db.execute("SET CONSTRAINTS ALL IMMEDIATE")
            before = {
                r["profile_key"]: dict(r)
                for r in db.execute("SELECT * FROM environmental_runtime_profiles")
            }
            self.assertEqual(len(before), 970)
            db.execute("SET CONSTRAINTS ALL DEFERRED")
            db.execute(seed_sql("environmental_destroy_profiles.sql"), prepare=False)
            db.execute("SET CONSTRAINTS ALL IMMEDIATE")
            after = {
                r["profile_key"]: dict(r)
                for r in db.execute("SELECT * FROM environmental_runtime_profiles")
            }
            self.assertEqual(len(after), 982)
            self.assertEqual({key: after[key] for key in before}, before)
            delta = sorted(set(after) - set(before))
            self.assertEqual(len(delta), 12)
            self.assertTrue(
                all(
                    after[key]["family"] == "monster_destroy"
                    and after[key]["sealed"]
                    and not after[key]["enabled"]
                    for key in delta
                )
            )
            rows = db.execute(
                "SELECT mode,count(*) AS n FROM environmental_runtime_profiles "
                "WHERE profile_key=ANY(%s) GROUP BY mode",
                (delta,),
            ).fetchall()
            self.assertEqual(
                {r["mode"]: r["n"] for r in rows},
                dict(solo=3, race=3, competitive=3, collaborative=3),
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM environmental_regional_schedule_candidates "
                    "WHERE version=7"
                ).fetchone()["n"],
                982,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM environmental_regional_schedule_policies "
                    "WHERE version=7 AND sealed AND NOT enabled"
                ).fetchone()["n"],
                90,
            )
            sources = db.execute(
                "SELECT * FROM environmental_destroy_sources WHERE policy_version='wakemu.explicit-public-target-native-destroy-v1'"
            ).fetchall()
            self.assertEqual(len(sources), 8)
            self.assertEqual(
                {(r["monster_reference"], r["action_id"]) for r in sources},
                {(2253, 265), (2236, 263)},
            )
            self.assertTrue(
                all(
                    r["action_descriptor"]["aGJ"] == 3
                    and r["action_descriptor"]["d"] == r["action_id"]
                    for r in sources
                )
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM environmental_random_roster_policies "
                    "WHERE native_type=5 AND scenario_id=ANY(%s)",
                    ([r["scenario_id"] for r in sources],),
                ).fetchone()["n"],
                8,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM environmental_profile_destroy_policy WHERE policy_version='wakemu.explicit-public-target-native-destroy-v1'"
                ).fetchone()["n"],
                12,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM environmental_profile_native_variable_bindings "
                    "WHERE profile_key=ANY(%s)",
                    (delta,),
                ).fetchone()["n"],
                150,
            )
            missing = db.execute(
                """SELECT p.profile_key FROM environmental_profile_native_variable_policy p
                JOIN environmental_native_variables v ON v.source_key=p.source_key AND v.scenario_id=p.native_scenario_id
                LEFT JOIN environmental_profile_native_variable_bindings b ON b.profile_key=p.profile_key
                  AND b.version=p.version AND b.variable_index=v.ordinal AND b.native_name=v.native_name
                WHERE p.profile_key=ANY(%s) AND b.profile_key IS NULL""",
                (delta,),
            ).fetchall()
            self.assertEqual(missing, [])
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
            for table in (
                "environmental_destroy_rosters",
                "environmental_monster_destructions",
                "environmental_destroy_publications",
            ):
                self.assertEqual(
                    db.execute("SELECT count(*) AS n FROM " + table).fetchone()["n"], 0
                )
            if named:
                prior = after
                db.execute("SET CONSTRAINTS ALL DEFERRED")
                db.execute(
                    seed_sql("environmental_named_destroy_profiles.sql"), prepare=False
                )
                db.execute("SET CONSTRAINTS ALL IMMEDIATE")
                installed = {
                    r["profile_key"]: dict(r)
                    for r in db.execute("SELECT * FROM environmental_runtime_profiles")
                }
                self.assertEqual(len(installed), 1262)
                self.assertEqual({key: installed[key] for key in prior}, prior)
                extra = sorted(set(installed) - set(prior))
                self.assertEqual(len(extra), 280)
                self.assertTrue(
                    all(
                        installed[key]["family"] == "monster_destroy"
                        and installed[key]["sealed"]
                        and not installed[key]["enabled"]
                        for key in extra
                    )
                )
                policy = "wakemu.original-body-namedtype-compatible-variant-v1"
                named_sources = db.execute(
                    "SELECT scenario_id,monster_reference,action_id,action_descriptor "
                    "FROM environmental_destroy_sources WHERE policy_version=%s",
                    (policy,),
                ).fetchall()
                self.assertEqual(len(named_sources), 236)
                self.assertEqual(
                    len({r["monster_reference"] for r in named_sources}), 53
                )
                self.assertTrue(
                    all(
                        r["action_descriptor"]["aGJ"] == 3
                        and r["action_descriptor"]["d"] == r["action_id"]
                        for r in named_sources
                    )
                )
                self.assertTrue(
                    {-1749, -1748, -1747, -1746}.isdisjoint(
                        r["scenario_id"] for r in named_sources
                    )
                )
                self.assertEqual(
                    db.execute(
                        "SELECT count(*) AS n FROM environmental_profile_destroy_policy "
                        "WHERE policy_version=%s",
                        (policy,),
                    ).fetchone()["n"],
                    280,
                )
                self.assertEqual(
                    db.execute(
                        "SELECT count(*) AS n FROM environmental_profile_native_variable_bindings "
                        "WHERE profile_key=ANY(%s)",
                        (extra,),
                    ).fetchone()["n"],
                    3500,
                )
                self.assertEqual(
                    db.execute(
                        "SELECT count(*) AS n FROM environmental_regional_schedule_candidates "
                        "WHERE version=8"
                    ).fetchone()["n"],
                    1262,
                )
                self.assertEqual(
                    db.execute(
                        "SELECT count(*) AS n FROM environmental_regional_schedule_policies "
                        "WHERE version=8 AND sealed AND NOT enabled"
                    ).fetchone()["n"],
                    90,
                )
                missing = db.execute(
                    """SELECT p.profile_key FROM environmental_profile_native_variable_policy p
                    JOIN environmental_native_variables v ON v.source_key=p.source_key AND v.scenario_id=p.native_scenario_id
                    LEFT JOIN environmental_profile_native_variable_bindings b ON b.profile_key=p.profile_key
                      AND b.version=p.version AND b.variable_index=v.ordinal AND b.native_name=v.native_name
                    WHERE p.profile_key=ANY(%s) AND b.profile_key IS NULL""",
                    (extra,),
                ).fetchall()
                self.assertEqual(missing, [])
                self.assertEqual(
                    db.execute(
                        "SELECT count(*) AS n FROM environmental_runtime_profiles "
                        "WHERE enabled OR NOT sealed"
                    ).fetchone()["n"],
                    0,
                )
            self.assertEqual(
                [
                    dict(r)
                    for r in db.execute(
                        "SELECT * FROM environmental_random_roster_versions ORDER BY policy_version"
                    )
                ],
                sizing,
            )
            self.assertEqual(
                dict(
                    db.execute(
                        "SELECT * FROM environmental_random_roster_active WHERE singleton"
                    ).fetchone()
                ),
                active,
            )
