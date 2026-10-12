"""Unpublished durable births reserve map/instance monster capacity."""
from postgres_case import PostgresCase
from psycopg.types.json import Jsonb
from wakfu_server import monster_population_capacity as capacity


class MonsterPopulationCapacityTests(PostgresCase):
    def test_unpublished_births_count_once_and_are_scoped_to_private_instance(self):
        with self.store.connection() as db:
            for uid, group_id, instance, published in (
                (1, 7, 0, False),
                (2, 8, 0, False),
                (3, 8, 0, False),
                (4, 9, 1, False),
                (5, 10, 0, True),
            ):
                db.execute(
                    "INSERT INTO planting_growth_outbox(resource_uid,resource,group_payload,published) VALUES(%s,%s,%s,%s)",
                    (
                        uid,
                        Jsonb(dict(map_id=1134, instance_id=instance)),
                        Jsonb(
                            dict(
                                key=[1134, instance, group_id],
                                members=[dict(id=-group_id)],
                            )
                        ),
                        published,
                    ),
                )
            counts = capacity.snapshot(
                db, 1134, 0, groups=[dict(group_id=7, members=[dict(id=-7)])]
            )
            self.assertEqual((counts["members"], counts["group_count"]), (2, 2))
            self.assertEqual([group["key"][2] for group in counts["reservations"]], [8])
            self.assertFalse(
                capacity.has_capacity(
                    counts, add_members=1, add_groups=1, max_members=2, max_groups=2
                )
            )
            private = capacity.snapshot(db, 1134, 1, groups=[])
            self.assertEqual((private["members"], private["group_count"]), (1, 1))

    def test_pending_birth_reservation_blocks_growth_without_consuming_seed(self):
        from wakfu_server import planting
        from wakfu_server.planting_runtime import Plantings

        reference = planting.SEEDS[30927]["resource_reference"]
        resource = dict(
            resource_uid=99,
            map_id=1134,
            instance_id=0,
            x=1,
            y=2,
            z=0,
            resource_reference=reference,
            stage=1,
            creation_time=0,
        )
        with self.store.connection() as db:
            policy = db.execute(
                "SELECT value FROM settings WHERE name='monster_reproduction'"
            ).fetchone()["value"]
            policy.update(max_zone_members=1, max_zone_groups=1)
            db.execute(
                "UPDATE settings SET value=%s WHERE name='monster_reproduction'",
                (Jsonb(policy),),
            )
            db.execute(
                "INSERT INTO planted_resources(resource_uid,map_id,instance_id,x,y,z,resource_reference,stage,creation_time) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                tuple(resource.values()),
            )
            db.execute(
                "INSERT INTO planting_growth_outbox(resource_uid,resource,group_payload) VALUES(1,%s,%s)",
                (
                    Jsonb(dict(map_id=1134, instance_id=0)),
                    Jsonb(dict(key=[1134, 0, 7], members=[dict(id=-7)])),
                ),
            )
        result = Plantings(self.store).apply_growth_candidates(
            [(resource, planting.RESOURCES[reference], None)]
        )
        self.assertEqual(result["capacity_skipped"], [99])
        self.assertEqual(result["applied"], [])
        from wakfu_server import ecology_plants
        from wakfu_server.planting_runtime import monster_growth_member
        from wakfu_server.combat_groups import Groups

        runtime = Plantings(self.store)
        runtime.ecology_world_epoch = "capacity-boot"
        runtime.store.clock = lambda: 1000
        definition = planting.RESOURCES[reference]
        plan = dict(
            kind="resource_growth",
            world_epoch="capacity-boot",
            expected=resource,
            transition=None,
            member=monster_growth_member(resource, definition),
        )
        deferred = ecology_plants.apply(
            runtime,
            Groups(),
            plan,
            authorize_spawn=lambda _: True,
            publish=lambda _: self.fail("Blocked seed published"),
        )
        self.assertEqual(deferred["status"], "deferred")
        self.assertEqual(deferred["reason"], "capacity")
        with self.store.connection() as db:
            self.assertEqual(
                dict(
                    db.execute(
                        "SELECT * FROM planted_resources WHERE resource_uid=99"
                    ).fetchone()
                ),
                resource,
            )
            self.assertIsNone(
                db.execute(
                    "SELECT 1 FROM planting_growth_outbox WHERE resource_uid=99"
                ).fetchone()
            )
