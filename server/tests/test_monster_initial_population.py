from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
import unittest
from unittest.mock import patch
import copy
import json
import tempfile
from pathlib import Path

from postgres_case import PostgresCase
from psycopg.types.json import Jsonb
from wakfu_server import monster_initial_population
from wakfu_server.combat_group_store import PersistentGroups
from wakfu_server.monsters import REFERENCES, owned_instance
from wakfu_server import native_catalog


class MonsterInitialPopulationTests(PostgresCase):
    def setUp(self):
        super().setUp()
        self.map_id = 1134
        self.instance_id = 29
        self.region_id = 79001
        self.groups = PersistentGroups(self.store)
        self.locate = self._locate
        self.plan = [
            {
                "reference": 5008,
                "level": REFERENCES[5008]["min_level"],
                "x": 0,
                "y": 0,
                "z": 0,
            },
            {
                "reference": 5008,
                "level": REFERENCES[5008]["min_level"],
                "x": 1,
                "y": 0,
                "z": 0,
            },
        ]

    def _locate(self, map_id, x, y, z):
        return {"region_id": self.region_id if x != 2 else self.region_id + 1}

    def _seed(self, groups=None, plan=None, *, instance_id=None):
        return monster_initial_population.seed_zone(
            self.store,
            groups or self.groups,
            self.map_id,
            self.instance_id if instance_id is None else instance_id,
            self.region_id,
            self.plan if plan is None else plan,
            locate=self.locate,
        )

    def _markers(self):
        with self.store.connection() as db:
            return db.execute(
                "SELECT * FROM monster_initial_population ORDER BY map_id,instance_id,region_id"
            ).fetchall()

    def _groups(self, *, instance_id=None):
        with self.store.connection() as db:
            return db.execute(
                "SELECT * FROM combat_groups WHERE map_id=%s AND instance_id=%s ORDER BY group_id",
                (self.map_id, self.instance_id if instance_id is None else instance_id),
            ).fetchall()

    def _populate_region(self, count, *, region_id=None, status="available"):
        """Persist count valid living members across native-sized groups."""
        destination_region = self.region_id if region_id is None else region_id
        created = 0
        group_id = 99000
        while created < count:
            members = []
            for slot in range(min(8, count - created)):
                index = created + slot
                if destination_region == self.region_id:
                    x, y = 10 + index, 5
                else:
                    x, y = 2, 10 + index
                members.append(
                    owned_instance(
                        5008,
                        REFERENCES[5008]["min_level"],
                        -700000 - index,
                        map_id=self.map_id,
                        instance_id=self.instance_id,
                        x=x,
                        y=y,
                        z=0,
                    )
                )
            self.groups.register(self.map_id, self.instance_id, group_id, members)
            group_id += 1
            created += len(members)
        if status != "available":
            with self.store.connection() as db:
                db.execute(
                    "UPDATE combat_groups SET status=%s WHERE map_id=%s AND instance_id=%s "
                    "AND group_id BETWEEN 99000 AND %s",
                    (status, self.map_id, self.instance_id, group_id - 1),
                )

    def test_seed_marker_and_group_are_durable_and_defeat_never_refills(self):
        created = self._seed()
        self.assertFalse(created["duplicate"])
        self.assertEqual(2, len(created["members"]))
        self.assertTrue(all(member["id"] < 0 for member in created["members"]))
        self.assertEqual(1, len(self._markers()))
        self.assertEqual(1, len(self._groups()))

        with self.store.connection() as db:
            db.execute(
                "UPDATE combat_groups SET status='defeated' WHERE map_id=%s AND instance_id=%s",
                (self.map_id, self.instance_id),
            )
        restarted_groups = PersistentGroups(self.store, recover=True)
        duplicate = self._seed(restarted_groups)
        self.assertTrue(duplicate["duplicate"])
        self.assertEqual(created["key"][2], duplicate["marker"]["group_id"])
        self.assertEqual(1, len(self._groups()))
        self.assertEqual("defeated", self._groups()[0]["status"])

    def test_map_cap_defers_both_bootstraps_until_real_defeat_with_reserved_birth(self):
        from wakfu_server import monster_population_capacity as capacity

        original_load = native_catalog.load
        original_snapshot = monster_initial_population.snapshot
        for route in ("direct", "prepared"):
            with self.subTest(route=route):
                self.instance_id += 1
                with self.store.connection() as db:
                    policy = db.execute(
                        "SELECT value FROM settings WHERE name='monster_reproduction'"
                    ).fetchone()["value"]
                    policy["max_zone_members"] = 1500
                    db.execute(
                        "UPDATE settings SET value=%s WHERE name='monster_reproduction'",
                        (Jsonb(policy),),
                    )
                    db.execute(
                        "UPDATE settings SET value=jsonb_set(value,'{members_per_zone}','1') "
                        "WHERE name='monster_initial_population'"
                    )
                self._populate_region(1498, region_id=self.region_id + 1)
                member = owned_instance(
                    5008,
                    REFERENCES[5008]["min_level"],
                    -990001,
                    map_id=self.map_id,
                    instance_id=self.instance_id,
                    x=2,
                    y=2000,
                    z=0,
                )
                key = self.groups.register(
                    self.map_id, self.instance_id, 88000, [member]
                )
                reservation = dict(
                    key=[self.map_id, self.instance_id, 88001],
                    members=[dict(member, id=-990002, y=2001)],
                )
                with self.store.connection() as db:
                    for suffix in (1, 2):
                        db.execute(
                            "INSERT INTO planting_growth_outbox(resource_uid,resource,group_payload) "
                            "VALUES(%s,%s,%s)",
                            (
                                self.instance_id * 10 + suffix,
                                Jsonb(
                                    dict(
                                        map_id=self.map_id, instance_id=self.instance_id
                                    )
                                ),
                                Jsonb(reservation),
                            ),
                        )
                    self.assertEqual(
                        capacity.snapshot(db, self.map_id, self.instance_id)["members"],
                        1500,
                    )
                    before_sequence = dict(
                        db.execute(
                            "SELECT last_value,is_called FROM monster_entity_uid"
                        ).fetchone()
                    )
                plan = dict(
                    map_id=self.map_id,
                    instance_id=self.instance_id,
                    region_id=self.region_id,
                    members=self.plan[:1],
                )

                def load(path):
                    if Path(path).name == "initial-monster-population.json":
                        return dict(plans=[plan])
                    return original_load(path)

                def snapshot(db, map_id, instance_id, **kwargs):
                    kwargs.setdefault("locate", self.locate)
                    return original_snapshot(db, map_id, instance_id, **kwargs)

                def attempt():
                    if route == "direct":
                        return self._seed(plan=self.plan[:1])
                    proposal = monster_initial_population.prepare_zone(self.store, plan)
                    return monster_initial_population.apply_prepared(
                        self.store, self.groups, proposal
                    )

                with patch.object(
                    native_catalog, "load", side_effect=load
                ), patch.object(
                    monster_initial_population, "snapshot", side_effect=snapshot
                ):
                    if route == "direct":
                        with self.assertRaisesRegex(ValueError, "no map capacity"):
                            attempt()
                    else:
                        self.assertEqual(attempt(), "stale")
                    with self.store.connection() as db:
                        self.assertEqual(
                            before_sequence,
                            dict(
                                db.execute(
                                    "SELECT last_value,is_called FROM monster_entity_uid"
                                ).fetchone()
                            ),
                        )
                        self.assertIsNone(
                            db.execute(
                                "SELECT 1 FROM monster_initial_population WHERE map_id=%s AND instance_id=%s",
                                (self.map_id, self.instance_id),
                            ).fetchone()
                        )
                        self.assertIsNone(
                            db.execute(
                                "SELECT 1 FROM monster_initial_population_publication WHERE map_id=%s AND instance_id=%s",
                                (self.map_id, self.instance_id),
                            ).fetchone()
                        )
                    with self.store.connection() as db:
                        fight_id = db.execute(
                            "INSERT INTO combat_fights(status) VALUES('active') RETURNING id"
                        ).fetchone()["id"]
                    lease, _ = self.groups.claim(key, "capacity-defeat", fight_id)
                    self.assertTrue(self.groups.finish(lease, defeated=True))
                    with self.store.connection() as db:
                        self.assertEqual(
                            capacity.snapshot(db, self.map_id, self.instance_id)[
                                "members"
                            ],
                            1499,
                        )
                    applied = attempt()
                    if route == "direct":
                        self.assertFalse(applied["duplicate"])
                    else:
                        self.assertEqual(applied, "applied")
                    with self.store.connection() as db:
                        self.assertEqual(
                            capacity.snapshot(db, self.map_id, self.instance_id)[
                                "members"
                            ],
                            1500,
                        )
                        self.assertEqual(
                            db.execute(
                                "SELECT count(*) AS n FROM monster_initial_population WHERE map_id=%s AND instance_id=%s",
                                (self.map_id, self.instance_id),
                            ).fetchone()["n"],
                            1,
                        )

    def test_parallel_startup_for_same_region_commits_one_seed(self):
        other_registry = PersistentGroups(self.store)
        barrier = Barrier(2)

        def seed(registry):
            barrier.wait(timeout=10)
            return self._seed(registry)

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(seed, (self.groups, other_registry)))

        self.assertEqual(
            1, sum(not result.get("duplicate", False) for result in results)
        )
        self.assertEqual(1, sum(result.get("duplicate", False) for result in results))
        self.assertEqual(1, len(self._markers()))
        self.assertEqual(1, len(self._groups()))
        self.assertEqual(2, len(self._groups()[0]["members"]))

    def test_group_and_marker_rollback_together_if_marker_insert_fails(self):
        with self.store.connection() as db:
            db.execute(
                "CREATE FUNCTION reject_initial_population_marker() RETURNS trigger "
                "LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'marker write rejected'; END $$"
            )
            db.execute(
                "CREATE TRIGGER reject_initial_population_marker "
                "BEFORE INSERT ON monster_initial_population "
                "FOR EACH ROW EXECUTE FUNCTION reject_initial_population_marker()"
            )

        with self.assertRaisesRegex(Exception, "marker write rejected"):
            self._seed()
        self.assertEqual([], self._markers())
        self.assertEqual([], self._groups())
        with self.store.connection() as db:
            self.assertEqual(
                0,
                db.execute(
                    "SELECT count(*) AS n FROM combat_group_members WHERE map_id=%s AND instance_id=%s",
                    (self.map_id, self.instance_id),
                ).fetchone()["n"],
            )

    def test_existing_live_group_occupancy_blocks_plan_but_defeated_group_does_not(
        self,
    ):
        member = owned_instance(
            5008,
            REFERENCES[5008]["min_level"],
            -98001,
            map_id=self.map_id,
            instance_id=self.instance_id,
            x=0,
            y=0,
            z=0,
        )
        self.groups.register(self.map_id, self.instance_id, 98001, [member])
        with self.assertRaisesRegex(ValueError, "occupied"):
            self._seed()
        self.assertEqual([], self._markers())

        with self.store.connection() as db:
            db.execute(
                "UPDATE combat_groups SET status='defeated' WHERE map_id=%s AND instance_id=%s AND group_id=98001",
                (self.map_id, self.instance_id),
            )
        self.assertFalse(self._seed()["duplicate"])
        self.assertEqual(2, len(self._groups()))

    def test_capacity_counts_existing_members_at_other_cells_before_allocating_ids(
        self,
    ):
        self._populate_region(249)
        with self.assertRaisesRegex(ValueError, "exceeds existing regional capacity"):
            self._seed()
        self.assertEqual(0, len(self._markers()))
        self.assertEqual(32, len(self._groups()))
        with self.store.connection() as db:
            sequence = db.execute(
                "SELECT last_value,is_called FROM monster_entity_uid"
            ).fetchone()
        self.assertFalse(sequence["is_called"])

    def test_population_in_another_region_does_not_charge_this_regions_capacity(self):
        self._populate_region(249, region_id=self.region_id + 1)
        seeded = self._seed()
        self.assertFalse(seeded["duplicate"])
        self.assertEqual(2, len(seeded["members"]))
        marker = self._markers()[0]
        self.assertEqual(self.region_id, marker["region_id"])

    def test_defeated_population_is_excluded_from_startup_capacity(self):
        self._populate_region(249, status="defeated")
        seeded = self._seed()
        self.assertFalse(seeded["duplicate"])
        self.assertEqual(2, len(seeded["members"]))
        self.assertEqual(self.region_id, self._markers()[0]["region_id"])

    def test_unresolved_existing_member_rejects_without_allocating_identity(self):
        member = owned_instance(
            5008,
            REFERENCES[5008]["min_level"],
            -699999,
            map_id=self.map_id,
            instance_id=self.instance_id,
            x=99,
            y=7,
            z=0,
        )
        self.groups.register(self.map_id, self.instance_id, 98999, [member])

        def locate(map_id, x, y, z):
            if x == 99:
                raise ValueError("unresolved native surface")
            return self._locate(map_id, x, y, z)

        self.locate = locate
        with self.assertRaisesRegex(ValueError, "unresolved native regions"):
            self._seed()
        self.assertEqual([], self._markers())
        self.assertEqual(1, len(self._groups()))
        with self.store.connection() as db:
            sequence = db.execute(
                "SELECT last_value,is_called FROM monster_entity_uid"
            ).fetchone()
        self.assertFalse(sequence["is_called"])

    def test_existing_unassigned_native_member_does_not_block_region_seed(self):
        member = owned_instance(
            5008,
            REFERENCES[5008]["min_level"],
            -699999,
            map_id=self.map_id,
            instance_id=self.instance_id,
            x=99,
            y=7,
            z=0,
        )
        self.groups.register(self.map_id, self.instance_id, 98999, [member])

        def locate(map_id, x, y, z):
            if x == 99:
                return {"region_id": -1}
            return self._locate(map_id, x, y, z)

        self.locate = locate
        seeded = self._seed()
        self.assertFalse(seeded["duplicate"])
        self.assertEqual(2, len(seeded["members"]))
        self.assertEqual(self.region_id, self._markers()[0]["region_id"])
        self.assertEqual(2, len(self._groups()))

    def test_planted_resource_occupancy_blocks_seed_before_identity_allocation(self):
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO planted_resources(resource_uid,map_id,instance_id,x,y,z,"
                "resource_reference,stage,creation_time) VALUES(1,%s,%s,0,0,0,60,0,0)",
                (self.map_id, self.instance_id),
            )
        with self.assertRaisesRegex(ValueError, "planted resources"):
            self._seed()
        self.assertEqual([], self._markers())
        self.assertEqual([], self._groups())
        with self.store.connection() as db:
            sequence = db.execute(
                "SELECT last_value,is_called FROM monster_entity_uid"
            ).fetchone()
        self.assertFalse(sequence["is_called"])

    def test_invalid_plan_is_rejected_before_opening_database_or_allocating_ids(self):
        invalid_plans = (
            [{**self.plan[0], "level": True}, self.plan[1]],
            [{**self.plan[0], "x": True}, self.plan[1]],
            [{**self.plan[0], "z": 32768}, self.plan[1]],
            [
                {**self.plan[0], "level": REFERENCES[5008]["max_level"] + 1},
                self.plan[1],
            ],
        )
        with patch.object(
            self.store,
            "connection",
            side_effect=AssertionError("invalid plan reached SQL"),
        ):
            for plan in invalid_plans:
                with self.subTest(plan=plan), self.assertRaises(ValueError):
                    self._seed(plan=plan)

    def test_policy_disabled_is_noop_and_malformed_or_wrong_sized_policy_fails_closed(
        self,
    ):
        with self.store.connection() as db:
            db.execute(
                "UPDATE settings SET value=%s WHERE name='monster_initial_population'",
                (Jsonb({"version": 1, "enabled": False, "members_per_zone": 2}),),
            )
        self.assertTrue(self._seed()["disabled"])
        self.assertEqual([], self._markers())
        self.assertEqual([], self._groups())

        for policy in (
            {"version": True, "enabled": True, "members_per_zone": 2},
            {"version": 1, "enabled": 1, "members_per_zone": 2},
            {"version": 1, "enabled": True, "members_per_zone": True},
            {"version": 1, "enabled": True, "members_per_zone": 0},
            {"version": 1, "enabled": True, "members_per_zone": 9},
        ):
            with self.subTest(policy=policy):
                with self.store.connection() as db:
                    db.execute(
                        "UPDATE settings SET value=%s WHERE name='monster_initial_population'",
                        (Jsonb(policy),),
                    )
                with self.assertRaises(ValueError):
                    self._seed()
                self.assertEqual([], self._markers())
                self.assertEqual([], self._groups())

        with self.store.connection() as db:
            db.execute(
                "UPDATE settings SET value=%s WHERE name='monster_initial_population'",
                (Jsonb({"version": 1, "enabled": True, "members_per_zone": 1}),),
            )
        with self.assertRaisesRegex(ValueError, "policy"):
            self._seed()

    def test_invalid_native_family_region_geometry_and_positions_are_rejected(self):
        wrong_family = [dict(row, reference=2) for row in self.plan]
        duplicate_position = [self.plan[0], {**self.plan[1], "x": 0}]
        wrong_region = [self.plan[0], {**self.plan[1], "x": 2}]
        for plan in (wrong_family, duplicate_position, wrong_region):
            with self.subTest(plan=plan), self.assertRaises(ValueError):
                self._seed(plan=plan)
            self.assertEqual([], self._markers())
            self.assertEqual([], self._groups())

        with self.assertRaises(ValueError):
            self._seed(plan=[{**self.plan[0], "reference": 999999}, self.plan[1]])
        with self.assertRaises(ValueError):
            self._seed(plan=[{**self.plan[0], "x": True}, self.plan[1]])
        with self.assertRaises(ValueError):
            self._seed(plan=[{**self.plan[0], "extra": 1}, self.plan[1]])
        with self.assertRaises(ValueError):
            self._seed(plan=[self.plan[0]])
        self.assertEqual([], self._markers())
        self.assertEqual([], self._groups())

    def test_marker_scope_is_region_and_instance_specific(self):
        self._seed()
        other_instance = 30
        created = self._seed(instance_id=other_instance)
        self.assertFalse(created["duplicate"])
        self.assertEqual(2, len(self._markers()))
        self.assertEqual(
            {self.instance_id, other_instance},
            {row["instance_id"] for row in self._markers()},
        )

    def test_configured_pilot_catalog_has_unique_walkable_adjacent_native_plans(self):
        plans = monster_initial_population.configured_plans()
        catalog = json.loads(
            native_catalog.read_text(
                monster_initial_population.DATA_ROOT / "initial-monster-population.json"
            )
        )
        self.assertEqual(len(plans), len(catalog["plans"]))
        identities = {
            (row["map_id"], row["instance_id"], row["region_id"]) for row in plans
        }
        self.assertEqual(len(identities), len(plans))
        for plan in plans:
            self.assertEqual(plan["instance_id"], 0)
            self.assertEqual(len(plan["members"]), 2)
            self.assertNotEqual(
                tuple(plan["members"][0][key] for key in ("x", "y", "z")),
                tuple(plan["members"][1][key] for key in ("x", "y", "z")),
            )

    def test_current_catalog_seeds_all_regions_and_restart_never_refills_defeated(self):
        plans = monster_initial_population.configured_plans()
        self.assertEqual(len(plans), 93)
        self.assertEqual(sum(len(plan["members"]) for plan in plans), 186)
        outcomes = monster_initial_population.seed_configured(
            self.store, self.groups, report=lambda **_row: None
        )
        self.assertEqual(len(outcomes), len(plans))
        self.assertTrue(
            all(row["result"].get("duplicate") is False for row in outcomes)
        )
        markers = self._markers()
        self.assertEqual(len(markers), len(plans))
        with self.store.connection() as db:
            groups = db.execute(
                "SELECT * FROM combat_groups WHERE instance_id=0 ORDER BY map_id,group_id"
            ).fetchall()
        self.assertEqual(sum(len(group["members"]) for group in groups), 2 * len(plans))

        defeated = markers[0]
        with self.store.connection() as db:
            db.execute(
                "UPDATE combat_groups SET status='defeated' WHERE map_id=%s AND instance_id=%s AND group_id=%s",
                (defeated["map_id"], defeated["instance_id"], defeated["group_id"]),
            )
        restarted = PersistentGroups(self.store, recover=True)
        with patch(
            "wakfu_server.combat_terrain.map_geometry",
            side_effect=AssertionError("marked habitats must not reload geometry"),
        ):
            duplicate_outcomes = monster_initial_population.seed_configured(
                self.store, restarted, report=lambda **_row: None
            )
        self.assertTrue(
            all(row["result"].get("duplicate") for row in duplicate_outcomes)
        )
        self.assertEqual(self._markers(), markers)
        with self.store.connection() as db:
            after_groups = db.execute(
                "SELECT * FROM combat_groups WHERE instance_id=0 ORDER BY map_id,group_id"
            ).fetchall()
        self.assertEqual(
            sum(len(group["members"]) for group in after_groups), 2 * len(plans)
        )
        self.assertEqual(
            next(
                group["status"]
                for group in after_groups
                if group["group_id"] == defeated["group_id"]
                and group["map_id"] == defeated["map_id"]
            ),
            "defeated",
        )

    def test_seed_configured_skips_invalid_plan_without_marker_then_seeds_next_zone(
        self,
    ):
        plans = monster_initial_population.configured_plans()
        invalid = copy.deepcopy(plans[0])
        invalid["members"][0]["x"] = 1 << 31
        reports = []

        outcomes = monster_initial_population.seed_configured(
            self.store,
            self.groups,
            report=lambda **row: reports.append(row),
            plans=(invalid, plans[1]),
        )

        self.assertEqual(len(outcomes), 2)
        self.assertFalse(outcomes[0]["applied"])
        self.assertIn("Invalid", outcomes[0]["reason"])
        self.assertFalse(outcomes[1]["result"]["duplicate"])
        self.assertEqual(
            [(row["map_id"], row["region_id"]) for row in self._markers()],
            [(plans[1]["map_id"], plans[1]["region_id"])],
        )
        self.assertEqual(
            [row["event"] for row in reports],
            ["monster_initial_population_skipped", "monster_initial_population_ready"],
        )

    def test_configured_catalog_rejects_a_nonwalkable_cell_before_seeding(self):
        path = monster_initial_population.DATA_ROOT / "initial-monster-population.json"
        catalog = json.loads(native_catalog.read_text(path))
        catalog["plans"][0]["members"][0]["x"] = 2**31 - 1
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json") as temporary:
            json.dump(catalog, temporary)
            temporary.flush()
            with self.assertRaisesRegex(ValueError, "walkable native habitat"):
                monster_initial_population.configured_plans(Path(temporary.name))

    def test_restart_with_all_durable_markers_skips_geometry_and_never_refills(self):
        plans = monster_initial_population.configured_plans()
        for plan in plans:
            monster_initial_population.seed_zone(
                self.store,
                self.groups,
                plan["map_id"],
                plan["instance_id"],
                plan["region_id"],
                plan["members"],
            )
        before_markers = self._markers()
        before_groups = self.groups.snapshot()
        reports = []

        with patch(
            "wakfu_server.combat_terrain.map_geometry",
            side_effect=AssertionError("completed habitats must not reload geometry"),
        ):
            outcomes = monster_initial_population.seed_configured(
                self.store, self.groups, report=lambda **row: reports.append(row)
            )

        self.assertEqual(len(outcomes), len(plans))
        self.assertTrue(all(row["result"]["duplicate"] for row in outcomes))
        self.assertEqual(len(reports), len(plans))
        self.assertTrue(all(row["duplicate"] for row in reports))
        self.assertEqual(self._markers(), before_markers)
        self.assertEqual(self.groups.snapshot(), before_groups)

    def test_unmarked_region_still_requires_bidirectional_native_geometry(self):
        plans = monster_initial_population.configured_plans()
        for plan in plans[:-1]:
            monster_initial_population.seed_zone(
                self.store,
                self.groups,
                plan["map_id"],
                plan["instance_id"],
                plan["region_id"],
                plan["members"],
            )
        completed = {
            (row["map_id"], row["instance_id"], row["region_id"]) for row in plans[:-1]
        }
        pending = plans[-1]
        first, second = [
            tuple(member[key] for key in ("x", "y", "z"))
            for member in pending["members"]
        ]
        incomplete_geometry = {"cells": [first, second], "edges": [(first, second)]}
        with patch(
            "wakfu_server.combat_terrain.map_geometry",
            return_value=incomplete_geometry,
        ):
            with self.assertRaisesRegex(
                ValueError, "bidirectional native walking edge"
            ):
                monster_initial_population.configured_plans(
                    completed_habitats=completed
                )
        self.assertEqual(len(self._markers()), len(plans) - 1)
        self.assertNotIn(
            (pending["map_id"], pending["instance_id"], pending["region_id"]),
            {
                (row["map_id"], row["instance_id"], row["region_id"])
                for row in self._markers()
            },
        )


if __name__ == "__main__":
    unittest.main()
