import unittest
from collections import Counter

from postgres_case import PostgresCase
from wakfu_server import ecology_population
from wakfu_server.monsters import REFERENCES, owned_instance
from wakfu_server.planting import RESOURCES
from wakfu_server.combat_group_store import PersistentGroups


class EcologyPopulationTests(PostgresCase):
    def setUp(self):
        super().setUp()
        self.map_id = 1134
        self.instance_id = 23
        self.groups = PersistentGroups(self.store)
        self._resource_uid = 91000

    def _locate(self, map_id, x, y, z):
        if map_id != self.map_id:
            raise ValueError("unknown map")
        regions = {
            0: 79001,
            1: 79201,
            2: 79001,
            3: 79201,
            4: 79201,
            5: 79201,
            6: 79201,
        }
        region_id = regions.get(x)
        if region_id is None or z == 99:
            raise ValueError("unknown surface")
        return {"region_id": region_id}

    def _plant(self, x, *, resource_reference=60, stage=2, instance_id=None):
        self._resource_uid += 1
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO planted_resources(resource_uid,map_id,instance_id,x,y,z,"
                "resource_reference,stage,creation_time) VALUES(%s,%s,%s,%s,0,0,%s,%s,0)",
                (
                    self._resource_uid,
                    self.map_id,
                    self.instance_id if instance_id is None else instance_id,
                    x,
                    resource_reference,
                    stage,
                ),
            )
        return self._resource_uid

    def _member(self, ref, actor_id, x, *, instance_id=None):
        return owned_instance(
            ref,
            REFERENCES[ref]["min_level"],
            actor_id,
            map_id=self.map_id,
            instance_id=self.instance_id if instance_id is None else instance_id,
            x=x,
            y=0,
            z=0,
        )

    def _group(self, group_id, members, *, status="available"):
        key = self.groups.register(self.map_id, self.instance_id, group_id, members)
        if status == "fighting":
            with self.store.connection() as db:
                fight_id = db.execute(
                    "INSERT INTO combat_fights(status) VALUES('active') RETURNING id"
                ).fetchone()["id"]
                db.execute(
                    "UPDATE combat_groups SET status='fighting',generation=%s,fight_id=%s "
                    "WHERE map_id=%s AND instance_id=%s AND group_id=%s",
                    ("population-test", fight_id, *key),
                )
        elif status == "defeated":
            with self.store.connection() as db:
                db.execute(
                    "UPDATE combat_groups SET status='defeated' "
                    "WHERE map_id=%s AND instance_id=%s AND group_id=%s",
                    key,
                )

    def test_counts_exact_regions_scoped_instance_live_groups_and_plants(self):
        plant_family = RESOURCES[60]["family_id"]
        monster_family = REFERENCES[2]["family_id"]
        self.assertFalse(RESOURCES[60]["monster_resource"])

        self._plant(0)
        self._plant(1, resource_reference=139)
        self._plant(2, instance_id=24)
        self._plant(4, stage=0)
        self._plant(5, stage=16)
        # Seed resources represent an unplanted creature, not both a plant and
        # a living monster. It must be omitted from this ecology population.
        seed_reference = next(
            ref
            for ref, definition in RESOURCES.items()
            if definition["monster_resource"]
        )
        self._plant(6, resource_reference=seed_reference, stage=1)

        self._group(92001, [self._member(2, -92001, 0)])
        self._group(92002, [self._member(39, -92002, 1)], status="fighting")
        self._group(92003, [self._member(2, -92003, 1)], status="defeated")
        other_instance_member = self._member(2, -92004, 0, instance_id=24)
        self.groups.register(self.map_id, 24, 92004, [other_instance_member])

        with self.store.connection() as db:
            result = ecology_population.snapshot(
                db, self.map_id, self.instance_id, locate=self._locate
            )

        self.assertTrue(result["complete"])
        self.assertEqual([], result["unresolved"])
        self.assertEqual(
            Counter({plant_family: 1}),
            result["regions"][79001]["plant"],
        )
        self.assertEqual(
            Counter({monster_family: 1}), result["regions"][79001]["monster"]
        )
        self.assertEqual(
            Counter({RESOURCES[139]["family_id"]: 1}), result["regions"][79201]["plant"]
        )
        self.assertEqual(
            Counter({monster_family: 1}), result["regions"][79201]["monster"]
        )

    def test_unknown_native_surface_is_reported_and_snapshot_incomplete(self):
        self._plant(99)
        with self.store.connection() as db:
            result = ecology_population.snapshot(
                db, self.map_id, self.instance_id, locate=self._locate
            )
        self.assertFalse(result["complete"])
        self.assertEqual([("plant", 91001)], result["unresolved"])
        self.assertEqual({}, result["regions"])

    def test_rejects_invalid_scope_types_and_ranges(self):
        with self.store.connection() as db:
            for map_id, instance_id in (
                (True, 0),
                (0, 0),
                (self.map_id, True),
                (self.map_id, -1),
                (self.map_id, 2**63),
            ):
                with self.subTest(map_id=map_id, instance_id=instance_id):
                    with self.assertRaises(ValueError):
                        ecology_population.snapshot(
                            db, map_id, instance_id, locate=self._locate
                        )


if __name__ == "__main__":
    unittest.main()
