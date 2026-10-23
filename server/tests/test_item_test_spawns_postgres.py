"""PostgreSQL tests for original native administrator item30532 test spawns."""
import struct
import unittest
import uuid

from postgres_case import PostgresCase
from wakfu_server.combat_terrain import map_geometry
from wakfu_server.inventory_items import grant
from wakfu_server import item_test_spawns
from wakfu_server.combat_group_store import PersistentGroups


class NativeItemTestSpawnsPostgresTests(PostgresCase):
    def setUp(self):
        super().setUp()
        self.account = self.store.register(
            "item-spawn-admin-" + uuid.uuid4().hex[:10], "local-password"
        )["id"]
        self.character = self.store.create_character(self.account, "Spawn Tester")
        self.generation = self.store.begin_session(self.account)
        self.store.select_character(self.account, self.generation, self.character["id"])
        with self.store.connection() as db:
            db.execute("UPDATE accounts SET is_admin=true WHERE id=%s", (self.account,))
            db.execute(
                "UPDATE characters SET map_id=1134,instance_id=0,x=-4,y=-18,z=0 WHERE id=%s",
                (self.character["id"],),
            )
        self.character = self.store.character(self.account, self.character["id"])
        self.container = next(
            row["uid"]
            for row in self.character["inventory_containers"]
            if row["kind"] == 0
        )
        self.source = self._source(
            self.account, self.generation, self.character["id"], self.container
        )
        self.groups = PersistentGroups(self.store)
        self.geometry = map_geometry(1134)

    def _source(self, account, generation, character_id, container):
        return grant(
            self.store,
            account,
            generation,
            character_id,
            reference=30532,
            quantity=1,
            container=container,
            slot=0,
            allowed_references={30532},
        )

    def _use(
        self,
        groups=None,
        *,
        account=None,
        generation=None,
        character_id=None,
        uid=None,
        action=item_test_spawns.ACTION_ID
    ):
        return item_test_spawns.use(
            self.store,
            self.groups if groups is None else groups,
            self.account if account is None else account,
            self.generation if generation is None else generation,
            self.character["id"] if character_id is None else character_id,
            struct.pack(">iq", action, self.source["uid"] if uid is None else uid),
            in_fight=False,
            geometry=lambda _: self.geometry,
        )

    def test_admin_authority_reusable_source_one_live_group_geometry_and_expiration(
        self,
    ):
        geometry = map_geometry(1134)
        with self.assertRaises(ValueError):
            self._use(action=item_test_spawns.ACTION_ID + 1)
        stale = self.store.begin_session(self.account)
        self.store.select_character(self.account, stale, self.character["id"])
        with self.assertRaises(ValueError):
            self._use(generation=self.generation)
        self.generation = stale

        result = self._use()
        self.assertTrue(result["applied"])
        self.assertEqual(("bIk", 0), (result["native_class"], result["consumed"]))
        replay = self._use()
        self.assertFalse(replay["applied"])
        self.assertEqual(result["key"], replay["key"])
        member = result["world_packets"][0]
        with self.store.connection() as db:
            saved = db.execute(
                "SELECT g.members,g.status,t.source_uid,t.ended_at FROM combat_groups g "
                "JOIN developer_item_test_groups t USING(map_id,instance_id,group_id) "
                "WHERE g.map_id=1134 AND g.instance_id=0 AND g.group_id=%s",
                (result["key"][2],),
            ).fetchone()
            item = db.execute(
                "SELECT reference,quantity FROM inventory_items WHERE uid=%s",
                (self.source["uid"],),
            ).fetchone()
            self.assertEqual((30532, 1), (item["reference"], item["quantity"]))
            self.assertEqual(self.source["uid"], saved["source_uid"])
            self.assertEqual("available", saved["status"])
            actor = saved["members"][0]
            cells = {tuple(c) for c in geometry["cells"]}
            self.assertIn((actor["x"], actor["y"], actor["z"]), cells)
            from wakfu_server.combat_actor_snapshot import native_actor_catalog
            from wakfu_server.combat_obstacle_condition import footprint

            radius = native_actor_catalog()["npc_profiles"]["5518"]["physical_radius"]
            columns = {}
            for cell in cells:
                columns.setdefault(cell[:2], []).append(cell)
            for xy in footprint((actor["x"], actor["y"]), radius):
                self.assertEqual(1, len(columns.get(xy, ())))
                self.assertEqual(actor["z"], columns[xy][0][2])
            self.assertLessEqual(
                abs(actor["x"] - self.character["x"])
                + abs(actor["y"] - self.character["y"]),
                8,
            )
            self.assertEqual(5518, actor["ref"])
            db.execute(
                "UPDATE developer_item_test_groups SET expires_at=CURRENT_TIMESTAMP-interval '1 second' "
                "WHERE map_id=1134 AND instance_id=0 AND group_id=%s",
                (result["key"][2],),
            )
        removed = item_test_spawns.expire(self.store, self.groups)
        self.assertEqual(1, len(removed))
        with self.store.connection() as db:
            retired = db.execute(
                "SELECT g.status,t.ended_at FROM combat_groups g JOIN developer_item_test_groups t "
                "USING(map_id,instance_id,group_id) WHERE g.map_id=1134 AND g.group_id=%s",
                (result["key"][2],),
            ).fetchone()
        self.assertEqual("defeated", retired["status"])
        self.assertIsNotNone(retired["ended_at"])
        self.assertEqual(member, result["world_packets"][0])

    def test_nonadmin_rejected_and_fighting_expiry_and_finish_are_durable_and_replayable(
        self,
    ):
        guest = self.store.register(
            "spawn-guest-" + uuid.uuid4().hex[:10], "local-password"
        )["id"]
        guest_character = self.store.create_character(guest, "Guest Tester")
        guest_generation = self.store.begin_session(guest)
        self.store.select_character(guest, guest_generation, guest_character["id"])
        guest_container = next(
            row["uid"]
            for row in guest_character["inventory_containers"]
            if row["kind"] == 0
        )
        guest_item = self._source(
            guest, guest_generation, guest_character["id"], guest_container
        )
        with self.assertRaisesRegex(ValueError, "administrator"):
            self._use(
                account=guest,
                generation=guest_generation,
                character_id=guest_character["id"],
                uid=guest_item["uid"],
            )

        self.generation = self.store.begin_session(self.account)
        self.store.select_character(self.account, self.generation, self.character["id"])
        result = self._use()
        key = result["key"]
        with self.store.connection() as db:
            fight_id = db.execute(
                "INSERT INTO combat_fights(status) VALUES('active') RETURNING id"
            ).fetchone()["id"]
            db.execute(
                "UPDATE developer_item_test_groups SET expires_at=CURRENT_TIMESTAMP-interval '1 second' "
                "WHERE map_id=%s AND instance_id=%s AND group_id=%s",
                key,
            )
        lease, _members = self.groups.claim(key, self.generation, fight_id)
        with self.store.connection() as db:
            self.assertTrue(item_test_spawns.is_fight(db, fight_id))
            self.assertTrue(item_test_spawns.is_fight(db, fight_id))
        self.assertEqual((), item_test_spawns.expire(self.store, self.groups))
        with self.store.connection() as db:
            self.assertIsNone(
                db.execute(
                    "SELECT ended_at FROM developer_item_test_groups WHERE map_id=%s AND instance_id=%s AND group_id=%s",
                    key,
                ).fetchone()["ended_at"]
            )
            finished = item_test_spawns.finish(db, self.groups, lease)
            self.assertTrue(finished["applied"])
            self.assertTrue(item_test_spawns.is_fight(db, fight_id))
            ended = db.execute(
                "SELECT ended_at FROM developer_item_test_groups WHERE map_id=%s AND instance_id=%s AND group_id=%s",
                key,
            ).fetchone()["ended_at"]
            self.assertIsNotNone(ended)
            replay = item_test_spawns.finish(db, self.groups, lease)
            self.assertFalse(replay["applied"])
            self.assertEqual(
                ended,
                db.execute(
                    "SELECT ended_at FROM developer_item_test_groups WHERE map_id=%s AND instance_id=%s AND group_id=%s",
                    key,
                ).fetchone()["ended_at"],
            )

    def test_test_actor_is_not_ecological_population_but_real_neighbor_is(self):
        from wakfu_server import (
            ecology_population,
            monster_population_capacity,
            monster_population_cleanup,
            monster_initial_population,
            ecology_admin,
            ecology_admin_planner,
            monsters,
            npc_actor_identity,
            planting_cells,
        )
        from wakfu_server.combat_obstacle_condition import footprint
        from wakfu_server.combat_actor_snapshot import native_actor_catalog
        from unittest.mock import patch

        with self.store.connection() as db:
            predicted = item_test_spawns._position(
                db, self.character, self.geometry, ()
            )
        region_id = planting_cells.surface(1134, *predicted)["region_id"]
        self.assertGreater(region_id, 0)
        spawn_footprint = set(footprint(predicted, 1))
        candidates = sorted(
            (tuple(cell) for cell in self.geometry["cells"]),
            key=lambda cell: abs(cell[0] - self.character["x"])
            + abs(cell[1] - self.character["y"]),
            reverse=True,
        )
        spawn_cell = next(
            (
                cell
                for cell in candidates
                if cell[:2] != (self.character["x"], self.character["y"])
                and not set(footprint(cell, 1)) & spawn_footprint
                and planting_cells.surface(1134, *cell)["region_id"] == region_id
            ),
            None,
        )
        self.assertIsNotNone(spawn_cell)
        with self.store.connection() as db:
            identity = npc_actor_identity.allocate_block(db, 1)
        ordinary = monsters.owned_instance(
            5525,
            monsters.reference(5525)["min_level"],
            -identity,
            map_id=1134,
            instance_id=0,
            x=spawn_cell[0],
            y=spawn_cell[1],
            z=spawn_cell[2],
        )
        ordinary_key = self.groups.register(1134, 0, identity, [ordinary])

        with self.store.connection() as db:
            before_ecology = ecology_population.snapshot(
                db, 1134, 0, kinds=("monster",)
            )
            before_capacity = monster_population_capacity.snapshot(db, 1134, 0)
            family = monsters.reference(5525)["family_id"]
            self.assertGreaterEqual(
                before_ecology["regions"][region_id]["monster"][family], 1
            )
            occupied_only = dict(
                self.geometry,
                cells=[spawn_cell],
                edges=[(spawn_cell, spawn_cell)],
            )
            with self.assertRaisesRegex(ValueError, "unoccupied"):
                item_test_spawns._position(db, self.character, occupied_only, ())

        spawned = self._use()
        self.assertTrue(spawned["applied"])
        test_group_id = spawned["key"][2]
        with self.store.connection() as db:
            after_ecology = ecology_population.snapshot(db, 1134, 0, kinds=("monster",))
            after_capacity = monster_population_capacity.snapshot(db, 1134, 0)
            test_member = db.execute(
                "SELECT members FROM combat_groups WHERE map_id=1134 AND instance_id=0 AND group_id=%s",
                (test_group_id,),
            ).fetchone()["members"][0]
            physical = monster_population_capacity.physical_cells(db, 1134, 0)
            radius = native_actor_catalog()["npc_profiles"]["5518"]["physical_radius"]
            self.assertTrue(
                {
                    (x, y, test_member["z"])
                    for x, y in footprint((test_member["x"], test_member["y"]), radius)
                }
                <= physical
            )
        self.assertEqual(before_ecology["regions"], after_ecology["regions"])
        self.assertEqual(before_capacity, after_capacity)

        captured = {}

        def capture_plan(map_id, region, counts, occupied, **kwargs):
            captured["occupied"] = set(occupied)
            captured["counts"] = dict(counts)
            return []

        with self.store.connection() as db, patch.object(
            ecology_admin_planner, "plan_groups", side_effect=capture_plan
        ):
            ecology_admin._genesis(db, self.groups, 1134, 0, region_id, players=())
        self.assertTrue(
            {
                (x, y, test_member["z"])
                for x, y in footprint((test_member["x"], test_member["y"]), radius)
            }
            <= captured["occupied"]
        )

        with patch.object(
            monster_initial_population,
            "REGIONS",
            {(1134, region_id): {"monster_capacity": 10}},
        ), patch.object(monster_population_cleanup, "_SCAN_STATE", None), patch.object(
            monster_population_cleanup, "certified_unassigned", return_value=True
        ):
            proposals = monster_population_cleanup.prepare(
                self.store,
                {"planning_tick": True, "world_epoch": "item30532-test"},
                limit=16,
                clock=lambda: 10.0,
            )
        proposed_ids = {proposal["group_id"] for proposal in proposals}
        self.assertIn(ordinary_key[2], proposed_ids)
        self.assertNotIn(test_group_id, proposed_ids)

        # Exercise the legacy (unprepared) reproduction path against the same
        # durable test actor. Its native edge list deliberately offers the
        # occupied test cell first; the domain must filter it using actual
        # physical_cells before selecting a destination.
        from wakfu_server import monster_reproduction, npc_actor_identity
        from wakfu_server.monsters import owned_instance, reference as monster_reference
        from unittest.mock import patch

        with self.store.connection() as db:
            magnitude = npc_actor_identity.allocate_block(db, 1)
        parent_id = -magnitude
        parent_position = (test_member["x"] - 1, test_member["y"], test_member["z"])
        parent = owned_instance(
            4,
            monster_reference(4)["min_level"],
            parent_id,
            map_id=1134,
            instance_id=0,
            x=parent_position[0],
            y=parent_position[1],
            z=parent_position[2],
        )
        parent_key = self.groups.register(1134, 0, magnitude, [parent])
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO monster_reproduction_timers(map_id,instance_id,monster_id,reference,"
                "remaining_ms,due,cycle) VALUES(1134,0,%s,4,0,true,1)",
                (parent_id,),
            )
        configuration = {
            "interval_ms": 1000,
            "birth_probability": 1.0,
            "birth_stage_decay": 1.0,
            "new_group_probability": 0.0,
            "max_members": 8,
            "max_zone_members": 128,
            "max_zone_groups": 32,
        }
        ticket = {
            "map_id": 1134,
            "instance_id": 0,
            "monster_id": parent_id,
            "cycle": 1,
            "group_id": parent_key[2],
            "reference": 4,
        }
        occupied_destination = (test_member["x"], test_member["y"], test_member["z"])
        free_destination = (test_member["x"] + 2, test_member["y"], test_member["z"])
        selected = {}

        def choose_destination(candidates):
            selected.setdefault("calls", []).append(list(candidates))
            return candidates[0]

        with patch(
            "wakfu_server.monster_habitat_cells.habitat_destination_allowed",
            return_value=True,
        ):
            receipt = monster_reproduction.attempt(
                self.store,
                ticket,
                present=True,
                indexed=(
                    None,
                    {parent_position: [occupied_destination, free_destination]},
                ),
                players=(),
                excluded_ids=(),
                draw=0.0,
                group_draw=0.5,
                choose=choose_destination,
                configuration=configuration,
            )
        self.assertEqual([free_destination], selected["calls"][0])
        self.assertEqual(
            free_destination,
            (receipt["child"]["x"], receipt["child"]["y"], receipt["child"]["z"]),
        )


def load_tests(loader, tests, pattern):
    suite = unittest.TestSuite()
    suite.addTests(loader.loadTestsFromTestCase(NativeItemTestSpawnsPostgresTests))
    return suite
