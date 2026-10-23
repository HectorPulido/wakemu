"""Additive bomb-stage corpus and two real native one-second occupations."""
import struct
from unittest.mock import patch

from postgres_case import PostgresCase
from test_environmental_destroy_bulk_pipeline import (
    EnvironmentalDestroyBulkPipelineTests,
)
from test_environmental_group_bulk_pipeline import seed_sql
from wakfu_server import health_store, resource_collect
from wakfu_server.combat_terrain import map_geometry
from wakfu_server.planting_cells import cells
from wakfu_server.progression import XP_BY_LEVEL
from wakfu_server.wire import proto_field
from wakfu_server.world import World
from wakfu_server.objectives import environmental_presence as presence
from wakfu_server.objectives import environmental_service as service
from wakfu_server.objectives import environmental_storage as storage
from wakfu_server.objectives import environmental_resource_stage as stages


class EnvironmentalDeclaredResourceStagesTests(PostgresCase):
    def test_1270_profiles_preserve_source280_and_execute_both_native_bomb_stage1_occupations(
        self,
    ):
        EnvironmentalDestroyBulkPipelineTests.qualify_corpus(self, named=True)
        with self.store.connection() as db:

            def originals():
                return {
                    table: [
                        dict(r)
                        for r in db.execute(
                            "SELECT * FROM " + table + " ORDER BY 1,2,3"
                        )
                    ]
                    for table in (
                        "environmental_original_resources",
                        "environmental_original_resource_actions",
                        "environmental_scenario_resource_actions",
                    )
                }

            original = originals()
            self.assertEqual(
                len(original["environmental_original_resource_actions"]), 78
            )
            missing = [
                r
                for r in original["environmental_scenario_resource_actions"]
                if r["status"] == "missing_original_stage"
            ]
            self.assertEqual(len(missing), 8)
            self.assertTrue(all(r["native_step"] == 2 for r in missing))
            before = {
                r["profile_key"]: dict(r)
                for r in db.execute("SELECT * FROM environmental_runtime_profiles")
            }
            self.assertEqual(len(before), 1262)
            db.execute("SET CONSTRAINTS ALL DEFERRED")
            db.execute(
                seed_sql("environmental_resource_stage_profiles.sql"), prepare=False
            )
            db.execute("SET CONSTRAINTS ALL IMMEDIATE")
            self.assertEqual(originals(), original)
            after = {
                r["profile_key"]: dict(r)
                for r in db.execute("SELECT * FROM environmental_runtime_profiles")
            }
            self.assertEqual(len(after), 1270)
            self.assertEqual({key: after[key] for key in before}, before)
            extra = sorted(set(after) - set(before))
            self.assertEqual(len(extra), 8)
            self.assertTrue(
                all(not after[key]["enabled"] and after[key]["sealed"] for key in extra)
            )
            rows = db.execute(
                "SELECT mode,count(*) AS n FROM environmental_runtime_profiles WHERE profile_key=ANY(%s) GROUP BY mode",
                (extra,),
            ).fetchall()
            self.assertEqual(
                {r["mode"]: r["n"] for r in rows},
                dict(solo=2, collaborative=2, competitive=2, race=2),
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM environmental_profile_native_variable_bindings WHERE profile_key=ANY(%s)",
                    (extra,),
                ).fetchone()["n"],
                60,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM environmental_profile_resource_cells WHERE profile_key=ANY(%s)",
                    (extra,),
                ).fetchone()["n"],
                1868,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM environmental_regional_schedule_candidates WHERE version=9"
                ).fetchone()["n"],
                1270,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM environmental_regional_schedule_policies WHERE version=9 AND sealed AND NOT enabled"
                ).fetchone()["n"],
                90,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM environmental_resource_stage_actions"
                ).fetchone()["n"],
                2,
            )
            mappings = db.execute(
                "SELECT * FROM environmental_resource_stage_mappings ORDER BY scenario_id"
            ).fetchall()
            self.assertEqual(len(mappings), 8)
            for row in mappings:
                resolved = stages.resolve(db, row["source_key"], row["scenario_id"])
                self.assertEqual(
                    (resolved["source_native_step"], resolved["native_step"]), (2, 1)
                )
                self.assertIn(
                    (resolved["resource_reference"], resolved["action_id"]),
                    {(744, 2102), (730, 2091)},
                )
        clock = [self.store.clock()]
        self.store.clock = lambda: clock[0]
        account = self.store.register("native-bomb-stage", "test-password")["id"]
        character = self.store.create_character(account, "Native Bomb Owner")
        generation = self.store.begin_session(account)
        self.store.select_character(account, generation, character["id"])
        self.assertTrue(self.store.heartbeat(account, generation, ttl=1800))
        world = World(
            lambda _: b"", lambda _: b"", lambda *_: True, deliver_batch=lambda *_: True
        )
        active_world = patch.object(presence, "_world", world)
        active_world.start()
        self.addCleanup(active_world.stop)
        with self.store.connection() as db:
            db.execute(
                "UPDATE characters SET level=201 WHERE id=%s", (character["id"],)
            )
            db.execute(
                "UPDATE character_progression SET xp=%s WHERE character_id=%s",
                (XP_BY_LEVEL[201], character["id"]),
            )
        for scenario, map_id, region, reference, action, mode in (
            (-1880, 1252, 88601, 744, 2102, "solo"),
            (-1637, 1134, 79001, 730, 2091, "collaborative"),
        ):
            key = f"resource-native{scenario}-{map_id}-{region}"
            native_points = [
                (x, y, row["z"])
                for (x, y), rows in cells(map_id).items()
                for row in rows
                if row["region_id"] == region
            ]
            self.assertTrue(native_points)
            with self.store.connection() as db:
                db.execute(
                    "UPDATE characters SET map_id=%s,instance_id=0,x=%s,y=%s,z=%s WHERE id=%s",
                    (map_id, *native_points[-1], character["id"]),
                )
                db.execute(
                    "UPDATE environmental_runtime_profiles SET enabled=true WHERE profile_key=%s",
                    (key,),
                )
                db.execute(
                    "UPDATE environmental_regional_schedule_policies SET enabled=true WHERE version=9 AND map_id=%s AND region_id=%s",
                    (map_id, region),
                )
            actual = health_store.initialize(
                self.store, account, generation, character["id"]
            )
            world.join(generation, object(), actual)
            location = dict(map_id=map_id, instance_id=0, region_id=region)
            first = service.refresh(
                self.store,
                account,
                generation,
                character["id"],
                location=location,
                now_ms=int(clock[0] * 1000),
            )
            event_id = first["instances"][0]["instance_id"]
            with self.store.connection() as db:
                event = dict(
                    db.execute(
                        "SELECT * FROM environmental_event_instances WHERE instance_id=%s",
                        (event_id,),
                    ).fetchone()
                )
                profile = storage._event_profile(db, event)
                self.assertEqual((profile["profile_key"], profile["mode"]), (key, mode))
                resource = dict(
                    db.execute(
                        "SELECT p.* FROM planted_resources p "
                        "JOIN environmental_owned_resources r USING(resource_uid) WHERE r.instance_id=%s ORDER BY p.resource_uid LIMIT 1",
                        (event_id,),
                    ).fetchone()
                )
            self.assertEqual(
                (resource["resource_reference"], resource["stage"]), (reference, 1)
            )
            edges = {(tuple(a), tuple(b)) for a, b in map_geometry(map_id)["edges"]}
            target = tuple(resource[k] for k in ("x", "y", "z"))
            origin = next(source for source, end in sorted(edges) if end == target)
            with self.store.connection() as db:
                db.execute(
                    "UPDATE characters SET x=%s,y=%s,z=%s WHERE id=%s",
                    (*origin, character["id"]),
                )
            world.join(
                generation, object(), self.store.character(account, character["id"])
            )
            unsigned = lambda value: value if value >= 0 else value + (1 << 64)
            body = (
                proto_field(8, action)
                + proto_field(16, unsigned(resource["x"]))
                + proto_field(24, unsigned(resource["y"]))
            )
            prepared = resource_collect.prepare(
                self.store,
                account,
                generation,
                character["id"],
                body,
                reachable=lambda owner, row: (
                    tuple(owner[k] for k in ("x", "y", "z")),
                    tuple(row[k] for k in ("x", "y", "z")),
                )
                in edges,
            )
            self.assertEqual(prepared["resource"]["stage"], 1)
            self.assertEqual(prepared["rule"]["duration_ms"], 1000)
            ticket = resource_collect.reserve(self.store, account, generation, prepared)
            self.assertEqual(ticket["duration_ms"], 1000)
            completion = struct.pack(">Bh", 2, 3)
            with self.assertRaises(resource_collect.HarvestNotReady) as early:
                resource_collect.complete(self.store, ticket, completion)
            self.assertEqual(early.exception.completes_at, ticket["completes_at"])
            clock[0] = ticket["completes_at"].timestamp()
            completed = resource_collect.complete(self.store, ticket, completion)
            self.assertTrue(completed["applied"])
            self.assertTrue(completed["environmental_owned_publication"])
            self.assertEqual(
                (completed["outcome"]["xp"], completed["outcome"]["quantity"]), (0, 0)
            )
            self.assertFalse(
                resource_collect.complete(self.store, ticket, completion)["applied"]
            )
            with self.store.connection() as db:
                self.assertEqual(
                    storage._progress(db, event, character["id"]), {"resource": 1}
                )
                self.assertEqual(
                    db.execute(
                        "SELECT quantity FROM environmental_fact_receipts WHERE instance_id=%s",
                        (event_id,),
                    ).fetchone()["quantity"],
                    1,
                )
                self.assertEqual(
                    db.execute(
                        "SELECT count(*) AS n FROM environmental_reward_entitlements WHERE instance_id=%s",
                        (event_id,),
                    ).fetchone()["n"],
                    0,
                )
                self.assertEqual(
                    db.execute(
                        "SELECT count(*) AS n FROM resource_harvest_receipts WHERE token=%s",
                        (ticket["token"],),
                    ).fetchone()["n"],
                    1,
                )
                self.assertEqual(
                    db.execute(
                        "SELECT count(*) AS n FROM account_professions WHERE profession_id=0"
                    ).fetchone()["n"],
                    0,
                )
                self.assertEqual(
                    db.execute(
                        "SELECT count(*) AS n FROM personal_ecology_receipts"
                    ).fetchone()["n"],
                    0,
                )
        with self.store.connection() as db:
            self.assertEqual(originals(), original)
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM resource_harvest_receipts"
                ).fetchone()["n"],
                2,
            )
            self.assertEqual(
                db.execute(
                    "SELECT xp FROM character_progression WHERE character_id=%s",
                    (character["id"],),
                ).fetchone()["xp"],
                XP_BY_LEVEL[201],
            )
