"""Four original criterion-bearing resources use persisted effective levels."""
import struct
import unittest
import hashlib
from pathlib import Path

import psycopg

from wakfu_server import builds, resource_collect
from wakfu_server.planting_cells import cells
from wakfu_server.progression import XP_BY_LEVEL
from wakfu_server.wire import proto_field
from wakfu_server.objectives import environmental_service as service
from wakfu_server.objectives import environmental_storage as storage
from wakfu_server.objectives import environmental_resource_population as population


class EnvironmentalResourceActionCriteriaTests(unittest.TestCase):
    def test_four_original_sources_recheck_persisted_effective_level_at_reserve_and_complete(
        self,
    ):
        from test_environmental_owned_resource_population import (
            EnvironmentalOwnedResourcePopulationTests,
        )

        fixture = EnvironmentalOwnedResourcePopulationTests(
            methodName="test_original_population_real_profession_zero_occupation_and_atomic_cleanup"
        )
        self.addCleanup(fixture.doCleanups)
        fixture.setUp()
        store = fixture.store
        identity = fixture.character["id"]
        points = list(
            dict.fromkeys(
                (x, y, row["z"])
                for (x, y), rows in cells(1276).items()
                for row in rows
                if row["region_id"] == 89901
            )
        )
        self.assertGreaterEqual(len(points), 432)
        source = "installed-environmental-source-v1"
        scenario_ids = (-1953, -1949, -1945, -1941)
        expected = {
            -1953: ("collaborative", 100, 5),
            -1949: ("competitive", 200, 10),
            -1945: ("race", 3, 1),
            -1941: ("solo", 200, 10),
        }
        with store.connection() as db:
            db.execute("UPDATE characters SET level=245 WHERE id=%s", (identity,))
            db.execute(
                "UPDATE character_progression SET xp=%s WHERE character_id=%s",
                (XP_BY_LEVEL[245], identity),
            )
            catalog = db.execute(
                "SELECT catalog_revision FROM environmental_resource_action_source_versions "
                "WHERE source_key=%s",
                (source,),
            ).fetchone()["catalog_revision"]
            originals = {}
            for scenario in scenario_ids:
                action = dict(
                    db.execute(
                        "SELECT b.*,a.action_id,a.original_action FROM "
                        "environmental_scenario_resource_actions b JOIN environmental_original_resource_actions a "
                        "USING(source_key,resource_reference,native_step,action_ordinal) "
                        "WHERE b.source_key=%s AND b.scenario_id=%s",
                        (source, scenario),
                    ).fetchone()
                )
                config = {
                    r["normalized_key"]: r["native_value"]
                    for r in db.execute(
                        "SELECT normalized_key,native_value FROM environmental_native_configuration "
                        "WHERE source_key=%s AND scenario_id=%s",
                        (source, scenario),
                    )
                }
                self.assertEqual(
                    (
                        action["resource_reference"],
                        action["native_step"],
                        action["action_id"],
                    ),
                    (757, 2, 2118),
                )
                self.assertEqual(
                    action["original_action"]["criteria"], "GetLevel() >= 10"
                )
                self.assertEqual(
                    (
                        int(config["challengelevelmin"]),
                        int(config["challengelevelmax"]),
                    ),
                    (201, 245),
                )
                self.assertEqual(
                    (
                        int(config["ressourcequantitytospawn"]),
                        int(config["nbresourceforreward"]),
                    ),
                    expected[scenario][1:],
                )
                originals[scenario] = (action, config)
            for text, result in (
                ("", None),
                ("GetLevel() >= 10", 10),
                (" \tGetLevel() >= 32767\r\n", 32767),
            ):
                self.assertEqual(
                    db.execute(
                        "SELECT environmental_resource_criterion_minimum(%s) AS n",
                        (text,),
                    ).fetchone()["n"],
                    result,
                )
            for text in (
                None,
                "GetLevel() >= -1",
                "GetLevel() >= 10.5",
                "GetLevel() >= 32768",
                "GetLevel() >= 10 && True",
                "GetLevel() > 10",
            ):
                with self.subTest(predicate=text), self.assertRaises(
                    psycopg.Error
                ), db.transaction():
                    db.execute(
                        "SELECT environmental_resource_criterion_minimum(%s)", (text,)
                    )

        def effective(level):
            # Provision the existing owned build-sheet authority in SQL; the
            # production Store hydrates both real and effective level itself.
            sheet = b"".join(
                proto_field(tag, value)
                for tag, value in (
                    (8, 0),
                    (18, b"Criterion Level"),
                    (24, level),
                    (56, 0),
                    (64, 1),
                )
            )
            with store.connection() as db:
                db.execute(
                    "INSERT INTO character_builds VALUES(%s,0,%s,%s,%s,%s) "
                    "ON CONFLICT(character_id,build_index) DO UPDATE SET sheet=EXCLUDED.sheet",
                    (
                        identity,
                        sheet,
                        builds.EMPTY_EQUIPMENT,
                        b"",
                        builds.EMPTY_APTITUDES,
                    ),
                )
                db.execute(
                    "UPDATE character_build_selection SET active_index=0,revision=revision+1 WHERE character_id=%s",
                    (identity,),
                )
            hydrated = store.character(fixture.account, identity)
            self.assertEqual(
                (hydrated["level"], hydrated["effective_level"]), (245, level)
            )
            return hydrated

        def scope(instance):
            fixture.world.leave(identity, fixture.generation)
            with store.connection() as db:
                db.execute(
                    "UPDATE characters SET map_id=1276,instance_id=%s,x=%s,y=%s,z=%s WHERE id=%s",
                    (instance, *points[-1], identity),
                )
            fixture.character = store.character(fixture.account, identity)
            fixture.world.join(fixture.generation, object(), fixture.character)
            return dict(map_id=1276, instance_id=instance, region_id=89901)

        def profile(scenario, key, *, minimum, enabled=False):
            mode, quantity, personal = expected[scenario]
            _, config = originals[scenario]
            with store.connection() as db:
                db.execute(
                    "INSERT INTO environmental_runtime_profiles "
                    "(profile_key,version,native_scenario_id,family,mode,map_id,region_id,duration_ms,anchor_ms,"
                    "level_min,level_max,minimum_contribution,authority,source_sha256,catalog_revision) "
                    "VALUES(%s,1,%s,'resource_collect',%s,1276,89901,%s,%s,%s,245,%s,%s,%s,%s)",
                    (
                        key,
                        scenario,
                        mode,
                        int(config["challengeduration"]) * 1000,
                        int(fixture.clock[0] * 1000) - 1000,
                        minimum,
                        personal,
                        "test-declared level1 isolates action criterion"
                        if minimum == 1
                        else "original scenario level bounds; controlled component fixture",
                        "0" * 64,
                        catalog,
                    ),
                )
                db.execute(
                    "INSERT INTO environmental_profile_objectives VALUES "
                    "(%s,1,'collect','resource_collect',757,2118,2,'interaction',%s)",
                    (key, quantity if mode == "collaborative" else personal),
                )
                db.execute(
                    "INSERT INTO environmental_profile_rewards VALUES "
                    "(%s,1,0,'xp',NULL,1,'test-only component reward')",
                    (key,),
                )
                if mode in ("competitive", "race"):
                    db.execute(
                        "INSERT INTO environmental_profile_evaluation VALUES(%s,1,%s,1,%s,%s)",
                        (
                            key,
                            "score_at_deadline"
                            if mode == "competitive"
                            else "first_completion",
                            "character_id" if mode == "competitive" else "commit_order",
                            "test-declared evaluator; not original winner policy",
                        ),
                    )
                db.execute(
                    "INSERT INTO environmental_profile_resource_population VALUES "
                    "(%s,1,%s,'declared_native_cells','catalog_cvF','test-only exact native cells')",
                    (key, source),
                )
                for ordinal, point in enumerate(points[: 2 * quantity + 32]):
                    db.execute(
                        "INSERT INTO environmental_profile_resource_cells VALUES(%s,1,%s,%s,%s,%s)",
                        (key, ordinal, *point),
                    )
                db.execute(
                    "UPDATE environmental_runtime_profiles SET sealed=true,enabled=%s WHERE profile_key=%s",
                    (enabled, key),
                )
                db.execute("SET CONSTRAINTS ALL IMMEDIATE")

        def admit(key, location):
            snapshot = service.refresh(
                store,
                fixture.account,
                fixture.generation,
                identity,
                location=location,
                now_ms=int(fixture.clock[0] * 1000),
            )
            event_id = next(
                r["instance_id"]
                for r in snapshot["instances"]
                if r["profile_key"] == key
            )
            with store.connection() as db:
                event = dict(
                    db.execute(
                        "SELECT * FROM environmental_event_instances WHERE instance_id=%s",
                        (event_id,),
                    ).fetchone()
                )
                resources = [
                    dict(r)
                    for r in db.execute(
                        "SELECT p.* FROM planted_resources p "
                        "JOIN environmental_owned_resources o USING(resource_uid) WHERE o.instance_id=%s ORDER BY resource_uid",
                        (event_id,),
                    )
                ]
            return event, resources

        def prepare(resource):
            unsigned = lambda value: value if value >= 0 else value + (1 << 64)
            body = (
                proto_field(8, 2118)
                + proto_field(16, unsigned(resource["x"]))
                + proto_field(24, unsigned(resource["y"]))
            )
            return resource_collect.prepare(
                store,
                fixture.account,
                fixture.generation,
                identity,
                body,
                reachable=lambda *_: True,
            )

        def close(key, event, location):
            with store.connection() as db:
                storage.cancel(
                    db,
                    event["instance_id"],
                    reason="criterion component done",
                    now_ms=int(fixture.clock[0] * 1000),
                )
                population.cleanup(
                    db,
                    map_id=1276,
                    instance_id=location["instance_id"],
                    now_ms=int(fixture.clock[0] * 1000),
                    limit=1024,
                )
                db.execute(
                    "UPDATE environmental_runtime_profiles SET enabled=false WHERE profile_key=%s",
                    (key,),
                )

        # All four original source profiles retain their level201 boundary;
        # their explicit criterion-isolation clones below alone lower it to1.
        for scenario in scenario_ids:
            profile(scenario, f"criterion-source-{abs(scenario)}", minimum=201)
        effective(245)
        location = scope(0)
        with store.connection() as db:
            db.execute(
                "UPDATE environmental_runtime_profiles SET enabled=true WHERE profile_key='criterion-source-1953'"
            )
        event, resources = admit("criterion-source-1953", location)
        effective(9)
        with self.assertRaisesRegex(ValueError, "level is ineligible"):
            prepare(resources[0])
        close("criterion-source-1953", event, location)
        for index, scenario in enumerate(scenario_ids, 1):
            with self.subTest(scenario=scenario):
                effective(10)
                location = scope(index)
                key = f"criterion-isolated-{abs(scenario)}"
                profile(scenario, key, minimum=1, enabled=True)
                event, resources = admit(key, location)
                self.assertEqual(len(resources), expected[scenario][1])
                prepared = prepare(resources[0])
                effective(9)
                with self.assertRaises(ValueError):
                    resource_collect.reserve(
                        store, fixture.account, fixture.generation, prepared
                    )
                with store.connection() as db:
                    self.assertEqual(
                        db.execute(
                            "SELECT count(*) AS n FROM resource_harvest_occupations WHERE character_id=%s",
                            (identity,),
                        ).fetchone()["n"],
                        0,
                    )
                effective(10)
                prepared = prepare(resources[0])
                ticket = resource_collect.reserve(
                    store, fixture.account, fixture.generation, prepared
                )
                effective(9)
                fixture.clock[0] += ticket["duration_ms"] / 1000
                with self.assertRaises(ValueError):
                    resource_collect.complete(store, ticket, struct.pack(">Bh", 2, 3))
                with store.connection() as db:
                    self.assertIsNone(
                        db.execute(
                            "SELECT 1 FROM resource_harvest_receipts WHERE token=%s",
                            (ticket["token"],),
                        ).fetchone()
                    )
                    self.assertIsNotNone(
                        db.execute(
                            "SELECT 1 FROM resource_harvest_occupations WHERE token=%s",
                            (ticket["token"],),
                        ).fetchone()
                    )
                    self.assertIsNone(
                        db.execute(
                            "SELECT retired_at_ms FROM environmental_owned_resources WHERE resource_uid=%s",
                            (resources[0]["resource_uid"],),
                        ).fetchone()["retired_at_ms"]
                    )
                effective(10)
                committed = resource_collect.complete(
                    store, ticket, struct.pack(">Bh", 2, 3)
                )
                self.assertTrue(committed["applied"])
                self.assertFalse(
                    resource_collect.complete(store, ticket, struct.pack(">Bh", 2, 3))[
                        "applied"
                    ]
                )
                with store.connection() as db:
                    self.assertEqual(
                        db.execute(
                            "SELECT count(*) AS n FROM resource_harvest_receipts WHERE token=%s",
                            (ticket["token"],),
                        ).fetchone()["n"],
                        1,
                    )
                close(key, event, location)
        # Import and seal the complete five-file source corpus in this same
        # isolated schema after the focused occupations. Keeping generated
        # schedules uninstalled until here avoids substituting a fake scheduler
        # bypass for the deliberately declared criterion-isolation profiles.
        seeds = Path(__file__).resolve().parents[1] / "seeds"
        names = (
            "environmental_resource_profiles.sql",
            "environmental_resource_races.sql",
            "environmental_resource_competitions.sql",
            "environmental_resource_results.sql",
            "environmental_resource_level_criteria.sql",
        )
        self.assertEqual(
            hashlib.sha256((seeds / names[-1]).read_bytes()).hexdigest(),
            "364dbd64c421f95cc57699bf16cad7cac9fb8b8ea8461bdd8bdca38b19c864e7",
        )
        with store.connection() as db:
            for name in names:
                sql = (
                    (seeds / name)
                    .read_text()
                    .replace("\nBEGIN;\n", "\n")
                    .replace("\nCOMMIT;\n", "\n")
                )
                db.execute(sql, prepare=False)
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM environmental_runtime_profiles "
                    "WHERE profile_key LIKE 'resource-native-%'"
                ).fetchone()["n"],
                352,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(DISTINCT native_scenario_id) AS n FROM environmental_runtime_profiles "
                    "WHERE profile_key LIKE 'resource-native-%'"
                ).fetchone()["n"],
                304,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(DISTINCT (map_id,region_id)) AS n FROM "
                    "environmental_regional_schedule_policies"
                ).fetchone()["n"],
                88,
            )
            db.execute(
                "UPDATE environmental_runtime_profiles SET sealed=true WHERE NOT sealed"
            )
            db.execute(
                "UPDATE environmental_regional_schedule_policies SET sealed=true WHERE NOT sealed"
            )
            db.execute("SET CONSTRAINTS ALL IMMEDIATE")
            native = db.execute(
                "SELECT r.profile_key,r.native_scenario_id,r.mode,r.level_min,r.level_max,"
                "r.minimum_contribution,o.required_quantity FROM environmental_runtime_profiles r "
                "JOIN environmental_profile_objectives o USING(profile_key,version) "
                "WHERE r.profile_key=ANY(%s) ORDER BY r.native_scenario_id",
                ([f"resource-native-{abs(s)}-1276-89901" for s in scenario_ids],),
            ).fetchall()
            self.assertEqual(len(native), 4)
            for row in native:
                mode, quantity, personal = expected[row["native_scenario_id"]]
                self.assertEqual(
                    (
                        row["mode"],
                        row["level_min"],
                        row["level_max"],
                        row["minimum_contribution"],
                        row["required_quantity"],
                    ),
                    (
                        mode,
                        201,
                        245,
                        personal,
                        quantity if mode == "collaborative" else personal,
                    ),
                )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM environmental_runtime_profiles "
                    "WHERE profile_key LIKE 'resource-native-%' AND (enabled OR NOT sealed)"
                ).fetchone()["n"],
                0,
            )
