"""Public cadence additions preserve immutable, already earned spawn deadlines."""
import unittest

from psycopg import DatabaseError
from wakfu_server.combat_group_store import PersistentGroups
from wakfu_server.planting_cells import cells
from wakfu_server.objectives import environmental_archmonster_runtime as runtime


V1 = "wakemu.native-count-archmonster-world-birth-v1"
V2 = "wakemu.native-count-archmonster-world-birth-v2"
OVERRIDES = {
    -1043: (4280, 98, 1119, 78701, 9000000),
    -1022: (4097, 23, 546, 62201, 3600000),
}


class EnvironmentalArchmonsterCadenceUpgradeTests(unittest.TestCase):
    def test_61_public_cadences_preserve_59_and_both_existing_v1_birth_deadlines(self):
        from test_environmental_owned_resource_population import (
            EnvironmentalOwnedResourcePopulationTests,
        )

        fixture = EnvironmentalOwnedResourcePopulationTests(
            methodName="test_original_population_real_profession_zero_occupation_and_atomic_cleanup"
        )
        self.addCleanup(fixture.doCleanups)
        fixture.setUp()
        store, world = fixture.store, fixture.world
        groups = PersistentGroups(store)
        self.assertTrue(
            store.heartbeat(fixture.account, fixture.generation, ttl=200000)
        )
        with store.connection() as db:

            def rows(version):
                return {
                    r["scenario_id"]: dict(r)
                    for r in db.execute(
                        "SELECT * FROM archmonster_spawn_cadences WHERE policy_version=%s ORDER BY scenario_id",
                        (version,),
                    )
                }

            old, new = rows(V1), rows(V2)
            self.assertEqual((len(old), len(new)), (61, 61))
            self.assertEqual(
                sum(
                    r["authority_kind"] == "SOURCE_DERIVED_PUBLIC" for r in old.values()
                ),
                59,
            )
            self.assertTrue(
                all(
                    r["authority_kind"] == "SOURCE_DERIVED_PUBLIC" for r in new.values()
                )
            )
            for scenario, row in old.items():
                if scenario not in OVERRIDES:
                    self.assertEqual(
                        {k: v for k, v in row.items() if k != "policy_version"},
                        {
                            k: v
                            for k, v in new[scenario].items()
                            if k != "policy_version"
                        },
                    )
                else:
                    self.assertEqual(
                        (row["cooldown_ms"], row["authority_kind"]),
                        (14400000, "DECLARED_WAKEMU"),
                    )
                    self.assertEqual(
                        new[scenario]["cooldown_ms"], OVERRIDES[scenario][-1]
                    )
                    self.assertEqual(
                        new[scenario]["provenance"]["native_breed"],
                        OVERRIDES[scenario][0],
                    )
                    self.assertFalse(
                        new[scenario]["provenance"]["provenance"][
                            "original_client_frequency_proven"
                        ]
                    )
            active = dict(
                db.execute(
                    "SELECT * FROM archmonster_spawn_active WHERE singleton"
                ).fetchone()
            )
            self.assertEqual((active["policy_version"], active["enabled"]), (V2, False))
            source_snapshot = [
                dict(r)
                for r in db.execute(
                    "SELECT * FROM archmonster_spawn_sources ORDER BY scenario_id"
                )
            ]
            self.assertEqual(len(source_snapshot), 63)
            self.assertEqual(
                sum(r["blocked_by_membership"] for r in source_snapshot), 2
            )
            with self.assertRaises(DatabaseError), db.transaction():
                db.execute(
                    "UPDATE archmonster_spawn_cadences SET cooldown_ms=1 WHERE policy_version=%s",
                    (V1,),
                )
        start = fixture.now_ms
        for ordinal, (
            scenario,
            (breed, level, map_id, region_id, cooldown),
        ) in enumerate(OVERRIDES.items()):
            with self.subTest(scenario=scenario):
                points = [
                    (x, y, row["z"])
                    for (x, y), layers in cells(map_id).items()
                    for row in layers
                    if row["region_id"] == region_id
                ]
                self.assertTrue(points, "Actual native scope floor must exist")
                world.leave(fixture.character["id"], fixture.generation)
                with store.connection() as db:
                    db.execute(
                        "UPDATE characters SET map_id=%s,instance_id=0,x=%s,y=%s,z=%s WHERE id=%s",
                        (map_id, *points[-1], fixture.character["id"]),
                    )
                    db.execute(
                        "UPDATE archmonster_spawn_active SET policy_version=%s,enabled=true WHERE singleton",
                        (V1,),
                    )
                fixture.character = store.character(
                    fixture.account, fixture.character["id"]
                )
                world.join(fixture.generation, object(), fixture.character)
                location = dict(map_id=map_id, instance_id=0, region_id=region_id)

                def poll(at):
                    fixture.clock[0] = at / 1000
                    return runtime.poll(
                        store, world, groups, location=location, now_ms=at
                    )

                born = poll(start + ordinal * 20000000)
                self.assertEqual(len(born), 1)
                with store.connection() as db:
                    birth = dict(
                        db.execute(
                            "SELECT * FROM archmonster_spawn_births WHERE spawn_id=%s",
                            (born[0],),
                        ).fetchone()
                    )
                    self.assertEqual(
                        (
                            birth["scenario_id"],
                            birth["monster_reference"],
                            birth["native_level"],
                            birth["policy_version"],
                            birth["cooldown_ms"],
                        ),
                        (scenario, breed, level, V1, 14400000),
                    )
                    db.execute(
                        "UPDATE archmonster_spawn_active SET policy_version=%s WHERE singleton",
                        (V2,),
                    )
                    fight_id = db.execute(
                        "INSERT INTO combat_fights(status,fight_kind) VALUES('active','pve') RETURNING id"
                    ).fetchone()["id"]
                lease, _ = groups.claim(
                    (map_id, 0, birth["group_id"]), fixture.generation, fight_id
                )
                self.assertTrue(groups.finish(lease, defeated=True))
                # The new, shorter guide deadline has passed, but the immutable
                # v1 birth still owns its original four-hour cooldown.
                self.assertEqual(poll(birth["spawned_at_ms"] + cooldown), ())
                self.assertEqual(poll(birth["cooldown_until_ms"] - 1), ())
                with store.connection() as db:
                    self.assertEqual(
                        dict(
                            db.execute(
                                "SELECT * FROM archmonster_spawn_births WHERE spawn_id=%s",
                                (born[0],),
                            ).fetchone()
                        ),
                        birth,
                    )
                replacement = poll(birth["cooldown_until_ms"])
                self.assertEqual(len(replacement), 1)
                with store.connection() as db:
                    current = dict(
                        db.execute(
                            "SELECT * FROM archmonster_spawn_births WHERE spawn_id=%s",
                            (replacement[0],),
                        ).fetchone()
                    )
                    self.assertEqual(
                        (
                            current["scenario_id"],
                            current["monster_reference"],
                            current["policy_version"],
                            current["cooldown_ms"],
                        ),
                        (scenario, breed, V2, cooldown),
                    )
                    self.assertEqual(
                        current["cooldown_until_ms"],
                        current["spawned_at_ms"] + cooldown,
                    )
                    self.assertNotEqual(current["monster_id"], birth["monster_id"])
                    self.assertEqual(
                        db.execute(
                            "SELECT status FROM combat_groups WHERE map_id=%s AND instance_id=0 AND group_id=%s",
                            (map_id, birth["group_id"]),
                        ).fetchone()["status"],
                        "defeated",
                    )
                    fight_id = db.execute(
                        "INSERT INTO combat_fights(status,fight_kind) VALUES('active','pve') RETURNING id"
                    ).fetchone()["id"]
                lease, _ = groups.claim(
                    (map_id, 0, current["group_id"]), fixture.generation, fight_id
                )
                self.assertTrue(groups.finish(lease, defeated=True))
        with store.connection() as db:
            self.assertEqual(rows(V1), old)
            self.assertEqual(rows(V2), new)
            self.assertEqual(
                [
                    dict(r)
                    for r in db.execute(
                        "SELECT * FROM archmonster_spawn_sources ORDER BY scenario_id"
                    )
                ],
                source_snapshot,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM archmonster_spawn_births"
                ).fetchone()["n"],
                4,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM environmental_event_instances"
                ).fetchone()["n"],
                0,
            )
