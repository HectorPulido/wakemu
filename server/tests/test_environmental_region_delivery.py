"""Real harvest progress and owner publication follow the current region.

A uses original327/56601 resources and native actions. B56602 is explicitly a
second application-scope fixture, not a claim about map327 native geography.
Native527 region resolution is checked separately inside the same compound.
"""
import csv
import io
from pathlib import Path
from unittest.mock import patch
from psycopg.types.json import Jsonb
import struct
import unittest

import test_environmental_owned_resource_population as owned_fixture
from wakfu_server import native_catalog, resource_collect
from wakfu_server.objectives import environmental_service as service
from wakfu_server.objectives.environmental_world import SelectedEnvironmentalEvents


class EnvironmentalRegionDeliveryTests(unittest.TestCase):
    def test_region_switch_progress_headers_pending_results_and_global_owned_claim(
        self,
    ):
        f = owned_fixture.EnvironmentalOwnedResourcePopulationTests(
            "test_original_population_real_profession_zero_occupation_and_atomic_cleanup"
        )
        f.setUp()
        self.addCleanup(f.doCleanups)
        store = f.store
        with store.connection() as db:
            for key, region, scenario, family in (
                ("region-a", 56601, -1320, "resource_collect"),
                ("region-b", 56602, -1321, "resource_plant"),
            ):
                db.execute(
                    "INSERT INTO environmental_runtime_profiles(profile_key,version,native_scenario_id,family,mode,map_id,region_id,duration_ms,anchor_ms,level_min,level_max,authority,source_sha256,catalog_revision) "
                    "VALUES(%s,1,%s,%s,'collaborative',327,%s,900000,%s,81,245,'declared region delivery fixture',%s,%s)",
                    (
                        key,
                        scenario,
                        family,
                        region,
                        f.now_ms - 1000,
                        "0" * 64,
                        native_catalog.release(),
                    ),
                )
                db.execute(
                    "INSERT INTO environmental_profile_objectives VALUES(%s,1,'collect',%s,478,1190,2,'interaction',2)",
                    (key, family),
                )
                db.execute(
                    "INSERT INTO environmental_profile_rewards VALUES(%s,1,0,'xp',NULL,100,'test-only')",
                    (key,),
                )
                db.execute(
                    "INSERT INTO environmental_profile_publication VALUES(%s,1,%s,77,%s,0,'constant','declared native codec fixture')",
                    (key, scenario, region),
                )
                for lifecycle, ordinal in (
                    ("proposed", 0),
                    ("active", 1),
                    ("completed", 2),
                    ("expired", 2),
                    ("cancelled", 2),
                ):
                    db.execute(
                        "INSERT INTO environmental_profile_publication_states VALUES(%s,1,%s,%s)",
                        (key, lifecycle, ordinal),
                    )
                db.execute(
                    "INSERT INTO environmental_profile_variables VALUES(%s,1,0,'count','collect',NULL)",
                    (key,),
                )
                if key == "region-a":
                    db.execute(
                        "INSERT INTO environmental_profile_resource_population VALUES(%s,1,'installed-environmental-source-v1','declared_native_cells','catalog_cvF','test-only reconstructed placement policy')",
                        (key,),
                    )
                    for ordinal, point in enumerate(f.points[:200]):
                        db.execute(
                            "INSERT INTO environmental_profile_resource_cells VALUES(%s,1,%s,%s,%s,%s)",
                            (key, ordinal, *point),
                        )
                else:
                    db.execute(
                        "INSERT INTO environmental_profile_bindings VALUES(%s,1,'committed_planting','test-only')",
                        (key,),
                    )
                db.execute(
                    "UPDATE environmental_runtime_profiles SET sealed=true,enabled=true WHERE profile_key=%s",
                    (key,),
                )
        connection = SelectedEnvironmentalEvents()
        location_a = dict(f.location)
        location_b = dict(f.location, region_id=56602)

        def refresh(location):
            return service.refresh(
                store,
                f.account,
                f.generation,
                f.character["id"],
                location=location,
                now_ms=int(f.clock[0] * 1000),
            )

        def publish(location):
            f.batches.clear()
            connection.refresh(
                store,
                f.world,
                f.account,
                f.generation,
                f.character["id"],
                location=location,
                ready=True,
                checkpoint=lambda: None,
                now_ms=int(f.clock[0] * 1000),
            )
            return [
                struct.unpack_from(">i", body, 1)[0]
                for batch in f.batches
                for opcode, body in batch
                if opcode == 12549
            ]

        first = refresh(location_a)
        event_a = first["instances"][0]["instance_id"]
        self.assertIn(-1320, publish(location_a))
        with store.connection() as db:
            resources = db.execute(
                "SELECT p.* FROM planted_resources p JOIN environmental_owned_resources r USING(resource_uid) ORDER BY resource_uid"
            ).fetchall()
        self.assertGreaterEqual(len(resources), 2)
        self.assertLessEqual(len(resources), 100)

        # An owned settlement receipt is an explicit fixture premise, not a
        # paid-fight claim. Even a stale A membership cannot bypass frozen B
        # admission. Both monster and group facts pass the same real filter.
        from wakfu_server.objectives import environmental_gameplay as gameplay
        from wakfu_server.objectives import environmental_groups

        with store.connection() as db:
            db.execute(
                "INSERT INTO environmental_event_memberships(instance_id,entity_kind,entity_id,reference,source_key,spawn_owned) VALUES(%s,'monster',-900,1,'declared stale membership',false)",
                (event_a,),
            )
            db.execute(
                "INSERT INTO character_achievement_events(character_id,event_key,signature,payload) VALUES(%s,'fight:99001',%s,%s)",
                (
                    f.character["id"],
                    "0" * 64,
                    Jsonb(dict(fight_id=99001, original_monsters=[[-900, 1]])),
                ),
            )
            group_fact = gameplay.GameplayFact(
                "group_defeated",
                "fight:99001",
                f.account,
                f.character["id"],
                327,
                0,
                "group",
                -901,
                1,
                int(f.clock[0] * 1000),
                region_id=56601,
                fight_id=99001,
            )
            source_scene = dict(
                location_a,
                original_entities=[
                    dict(id=-900, ref=1, x=f.points[0][0], y=f.points[0][1])
                ],
            )
            with patch.object(
                environmental_groups, "winning_facts", return_value=(group_fact,)
            ):
                admitted_b = []
                gameplay.settled_fight(
                    db,
                    account_id=f.account,
                    character_id=f.character["id"],
                    fight_id=99001,
                    source_scene=dict(source_scene, region_id=56602),
                    deferred_facts=admitted_b,
                )
                self.assertEqual(admitted_b, [])
                admitted_a = []
                gameplay.settled_fight(
                    db,
                    account_id=f.account,
                    character_id=f.character["id"],
                    fight_id=99001,
                    source_scene=source_scene,
                    deferred_facts=admitted_a,
                )
                self.assertEqual(
                    {fact.kind for fact in admitted_a},
                    {"monster_defeated", "group_defeated"},
                )

        def harvest(row):
            ticket = f.ticket(dict(row))
            f.clock[0] += 5
            result = resource_collect.complete(store, ticket, struct.pack(">Bh", 2, 3))
            self.assertTrue(result["applied"])
            self.assertFalse(
                resource_collect.complete(store, ticket, struct.pack(">Bh", 2, 3))[
                    "applied"
                ]
            )

        # Native-region uncertainty rejects the action before a reservation;
        # restore the exact durable position before the real harvest below.
        with store.connection() as db:
            position = db.execute(
                "SELECT x,y,z FROM characters WHERE id=%s", (f.character["id"],)
            ).fetchone()
            db.execute(
                "UPDATE characters SET x=1000000,y=1000000 WHERE id=%s",
                (f.character["id"],),
            )
        with self.assertRaisesRegex(ValueError, "another native region"):
            f.ticket(dict(resources[0]))
        with store.connection() as db:
            db.execute(
                "UPDATE characters SET x=%s,y=%s,z=%s WHERE id=%s",
                (position["x"], position["y"], position["z"], f.character["id"]),
            )
        harvest(resources[0])
        resumed = refresh(location_a)["instances"][0]
        self.assertEqual(resumed["variables"], [dict(variable_index=0, value=1)])
        at_b = refresh(location_b)
        event_b = at_b["instances"][0]["instance_id"]
        self.assertNotEqual(event_b, event_a)
        self.assertEqual([row["instance_id"] for row in at_b["instances"]], [event_b])
        headers = publish(location_b)
        self.assertIn(-1321, headers)
        self.assertNotIn(-1320, headers)
        self.assertEqual(refresh(location_a)["instances"][0]["instance_id"], event_a)
        self.assertIn(-1320, publish(location_a))
        self.assertEqual(
            refresh(location_a)["instances"][0]["variables"],
            [dict(variable_index=0, value=1)],
        )
        harvest(resources[1])
        with store.connection() as db:
            pending = db.execute(
                "SELECT delivery_key FROM environmental_publication_outbox WHERE instance_id=%s AND kind='completed' AND acknowledged_at_ms IS NULL",
                (event_a,),
            ).fetchall()
        self.assertEqual(len(pending), 1)
        claimed_in_b = refresh(location_b)
        self.assertEqual(len(claimed_in_b["rewards"]["delivered"]), 1)
        self.assertTrue(
            all(
                row["kind"] == "claimed" or row["instance_id"] == event_b
                for row in claimed_in_b["deliveries"]
            )
        )
        self.assertNotIn(-1320, publish(location_b))
        with store.connection() as db:
            self.assertIsNone(
                db.execute(
                    "SELECT acknowledged_at_ms FROM environmental_publication_outbox WHERE delivery_key=%s",
                    (pending[0]["delivery_key"],),
                ).fetchone()["acknowledged_at_ms"]
            )
            claims = db.execute(
                "SELECT count(*) AS n FROM environmental_reward_entitlements WHERE claimed_at_ms IS NOT NULL"
            ).fetchone()["n"]
        self.assertEqual(claims, 1)
        back = refresh(location_a)
        self.assertTrue(
            any(
                row["delivery_key"] == pending[0]["delivery_key"]
                for row in back["deliveries"]
            )
        )
        self.assertIn(-1320, publish(location_a))
        self.assertEqual(refresh(location_a)["rewards"]["delivered"], [])
        with store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM resource_harvest_receipts"
                ).fetchone()["n"],
                2,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM environmental_participants WHERE instance_id=ANY(%s)",
                    ([event_a, event_b],),
                ).fetchone()["n"],
                2,
            )
        # Production native region resolver, independent of the declared B scope.
        from wakfu_server.objectives.environmental_gameplay import _native_region

        cells = list(
            csv.DictReader(
                io.StringIO(
                    Path(
                        ".runtime/parallel-readiness-20261021/environmental-original-native-cells.csv"
                    ).read_text()
                )
            )
        )
        for region in (76101, 75701):
            row = next(
                row
                for row in cells
                if int(row["map_id"]) == 527 and int(row["region_id"]) == region
            )
            self.assertEqual(
                _native_region(527, dict(x=int(row["x"]), y=int(row["y"]))), region
            )
