"""Actual planting and Ranch building placement share account-owned cells."""
import struct
import unittest
from datetime import timedelta

from postgres_case import PostgresCase


class RanchOccupancyPostgresTests(PostgresCase):
    def setUp(self):
        super().setUp()
        self.account = self.store.register("ranch-overlap", "test-password")["id"]
        self.character = self.store.create_character(self.account, "Ranch Overlap")
        self.generation = self.store.begin_session(self.account)
        self.character = self.store.select_character(
            self.account, self.generation, self.character["id"]
        )
        from wakfu_server.haven_bag import HavenBagSession
        from wakfu_server.haven_ranch import RanchSession, destination

        self.bag = HavenBagSession(self.character)
        self.ranch = RanchSession(
            self.bag,
            self.bag.inside,
            destination(35),
            lease=self.generation,
            now_ms=1000,
        )
        self.store.clock = lambda: self.now[0]
        self.now = [1000.0]
        from wakfu_server.planting import SEEDS
        from wakfu_server.planting_runtime import Plantings
        from wakfu_server.profession_store import ensure_learned

        ensure_learned(
            self.store, self.account, self.generation, self.character["id"], [72]
        )
        self.seed = SEEDS[4275]
        from wakfu_server.inventory_items import grant

        self.seed_item = grant(
            self.store,
            self.account,
            self.generation,
            self.character["id"],
            reference=4275,
            quantity=3,
            container=self.character["inventory_containers"][0]["uid"],
            slot=0,
            allowed_references=SEEDS,
        )
        from wakfu_server.haven_bag_garden import active_character, authorize

        self.garden = active_character
        self.authorize_garden = authorize
        self.runtime = Plantings(
            self.store,
            growth_seconds=30,
            # Planting outcome is caller-owned; keep this cell-occupancy test
            # deterministic without substituting climate/territory data.
            probability_context=lambda _prepared: 1.0,
            location_context=lambda stored: active_character(
                stored, [self.ranch.inside], store=self.store
            ),
        )
        from wakfu_server.haven_ranch_building_catalog import definition, mode
        from wakfu_server.ranch_native_geometry import validate_building_placement
        from wakfu_server.planting_cells import private_surfaces
        from wakfu_server.combat_terrain import map_geometry

        self.definition = definition(16)
        self.mode_id = mode(self.definition)["p"]
        self.private_surfaces = private_surfaces
        self.validate_building_placement = validate_building_placement
        self.edges = tuple(
            tuple(tuple(point) for point in edge)
            for edge in map_geometry(1440).get("edges", ())
        )
        self.cells = self._common_cells()
        self.assertGreaterEqual(
            len(self.cells), 3, "Need three actual shared Ranch cells"
        )

        # Learn the real native bIA source (item33110/action15152 -> plan16).
        source = grant(
            self.store,
            self.account,
            self.generation,
            self.character["id"],
            reference=33110,
            quantity=1,
            container=self.character["inventory_containers"][0]["uid"],
            slot=1,
            allowed_references={33110},
        )
        from wakfu_server import haven_ranch_building_knowledge

        result = haven_ranch_building_knowledge.learn(
            self.store,
            self.account,
            self.generation,
            self.character["id"],
            struct.pack(">iq", 15152, source["uid"]),
        )
        self.assertTrue(result["applied"])

    def _common_cells(self):
        from wakfu_server import planting_cells

        candidates = []
        for (x, y), surfaces in planting_cells.cells(1440).items():
            edge = next(
                (
                    start
                    for start, end in self.edges
                    if end[:2] == (x, y) and any(row["z"] == end[2] for row in surfaces)
                ),
                None,
            )
            if edge is None:
                continue
            try:
                exact = self.private_surfaces(1440, x, y)
                if len(exact) != 1:
                    continue
                self.validate_building_placement(
                    self.definition,
                    self.mode_id,
                    0,
                    1,
                    x,
                    y,
                    biome_id=1,
                    existing_buildings=(),
                    occupied_cells=(),
                )
            except ValueError:
                continue
            candidates.append(((x, y, exact[0]["z"]), edge))
        # Keep the two actual targets far apart so their native footprints and
        # child objects cannot interact through adjacency.
        chosen = []
        for item in candidates:
            if all(
                abs(item[0][0] - old[0][0]) + abs(item[0][1] - old[0][1]) >= 12
                for old in chosen
            ):
                chosen.append(item)
                if len(chosen) == 3:
                    break
        return chosen

    def _move_to_planting_neighbor(self, cell, edge):
        start = edge
        self.ranch.move(
            self.ranch.inside,
            {"x": start[0], "y": start[1], "z": start[2]},
        )

    def _plant(self, cell, edge, *, item_uid):
        from wakfu_server.planting import SEEDS

        self._move_to_planting_neighbor(cell, edge)
        body = struct.pack(
            ">iqii", SEEDS[4275]["action_id"], item_uid, cell[0], cell[1]
        )
        self.runtime.begin(
            self.account,
            self.generation,
            self.ranch.inside,
            body,
            lambda current, request, seed, resource: self.authorize_garden(
                self.store, current, request, seed, resource
            ),
        )
        return body

    def _place(self, cell):
        from wakfu_server import haven_ranch_buildings

        body = struct.pack(">iBiii", 16, 0, 1, cell[0], cell[1])
        return haven_ranch_buildings.operate(
            self.store,
            self.account,
            self.generation,
            self.ranch.inside,
            12671,
            body,
            session=self.ranch,
        )

    def _seed_quantity(self):
        with self.store.connection() as db:
            row = db.execute(
                "SELECT quantity FROM inventory_items WHERE uid=%s",
                (self.seed_item["uid"],),
            ).fetchone()
        return None if row is None else row["quantity"]

    def test_actual_building_and_planting_reject_each_other_but_not_other_accounts(
        self,
    ):
        first, second = self.cells[:2]
        # A committed native plant blocks the same account's building mask.
        self._plant(first[0], first[1], item_uid=self.seed_item["uid"])
        self.now[0] += 3
        self.runtime.complete(
            self.account, self.generation, self.ranch.inside, b"\x02\x00\x02"
        )
        before_buildings = self._building_rows(self.account)
        with self.assertRaisesRegex(ValueError, "overlaps an existing object"):
            self._place(first[0])
        self.assertEqual(self._building_rows(self.account), before_buildings)
        self.assertEqual(self._seed_quantity(), 2)

        # A plant begun before placement is rejected at its transactional
        # completion boundary, without consuming the reserved seed.
        body = self._plant(second[0], second[1], item_uid=self.seed_item["uid"])
        placed = self._place(second[0])
        self.assertTrue(placed["changed"])
        building_uid = placed["building"]["uid"]
        fixed_now = self.store.now()
        self.store.now = lambda offset_seconds=0: fixed_now + timedelta(
            seconds=offset_seconds
        )
        self._assert_component18_matches_scene(self.store, building_uid)
        reloaded = self.reopen()
        reloaded.now = lambda offset_seconds=0: fixed_now + timedelta(
            seconds=offset_seconds
        )
        self._assert_component18_matches_scene(reloaded, building_uid)

        # A second authentic bIA source and its retry must preserve the
        # already-placed fBG in account component18.
        from wakfu_server.inventory_items import grant
        from wakfu_server import haven_ranch_building_knowledge

        second_source = grant(
            reloaded,
            self.account,
            self.generation,
            self.character["id"],
            reference=33115,
            quantity=1,
            container=self.character["inventory_containers"][0]["uid"],
            slot=2,
            allowed_references={33115},
        )
        learned = haven_ranch_building_knowledge.learn(
            reloaded,
            self.account,
            self.generation,
            self.character["id"],
            struct.pack(">iq", 15157, second_source["uid"]),
        )
        self.assertTrue(learned["applied"])
        self._assert_component18_matches_scene(reloaded, building_uid)
        replay = haven_ranch_building_knowledge.learn(
            reloaded,
            self.account,
            self.generation,
            self.character["id"],
            struct.pack(">iq", 15157, second_source["uid"]),
        )
        self.assertFalse(replay["applied"])
        self._assert_component18_matches_scene(reloaded, building_uid)
        self.now[0] += 3
        with self.assertRaisesRegex(ValueError, "contains a native Ranch building"):
            self.runtime.complete(
                self.account, self.generation, self.ranch.inside, b"\x02\x00\x02"
            )
        self.runtime.cancel(self.character["id"], self.generation)
        self.assertEqual(self._seed_quantity(), 2)
        self.assertEqual(
            self._resource_rows(self.ranch.inside["instance_id"]), [first[0]]
        )

        # Move the surviving native building, reload its durable identity, and
        # remove that same UID through the native operation path.
        third = self.cells[2]
        from wakfu_server import haven_ranch_buildings

        moved = haven_ranch_buildings.operate(
            self.store,
            self.account,
            self.generation,
            self.ranch.inside,
            12662,
            struct.pack(">qBiii", building_uid, 0, 1, third[0][0], third[0][1]),
            session=self.ranch,
        )
        self.assertTrue(moved["changed"])
        self.assertEqual(moved["building"]["uid"], building_uid)
        reloaded = self.reopen()
        reloaded.now = lambda offset_seconds=0: fixed_now + timedelta(
            seconds=offset_seconds
        )
        with reloaded.connection() as db:
            durable = haven_ranch_buildings.rows(db, self.account, 1)
        self.assertEqual(len(durable), 1)
        self.assertEqual(
            (durable[0]["uid"], durable[0]["x"], durable[0]["y"]),
            (building_uid, third[0][0], third[0][1]),
        )
        self._assert_component18_matches_scene(reloaded, building_uid)
        removed = haven_ranch_buildings.operate(
            self.store,
            self.account,
            self.generation,
            self.ranch.inside,
            13480,
            struct.pack(">q", building_uid),
            session=self.ranch,
        )
        self.assertTrue(removed["changed"])
        self.assertEqual(removed["building"]["uid"], building_uid)
        with self.store.connection() as db:
            self.assertEqual(haven_ranch_buildings.rows(db, self.account, 1), [])
            tombstone = db.execute(
                "SELECT uid FROM account_ranch_building_tombstones WHERE uid=%s "
                "AND account_id=%s AND biome_id=1",
                (building_uid, self.account),
            ).fetchone()
        self.assertEqual(tombstone["uid"], building_uid)

        # A different account has a separate private instance and may use the
        # same map cell even while this account owns a building there.
        other_account = self.store.register("ranch-other-owner", "test-password")["id"]
        other_character = self.store.create_character(other_account, "Other ranch")
        other_generation = self.store.begin_session(other_account)
        other_character = self.store.select_character(
            other_account, other_generation, other_character["id"]
        )
        from wakfu_server.haven_bag import HavenBagSession
        from wakfu_server.haven_ranch import RanchSession, destination

        other_bag = HavenBagSession(other_character)
        other_ranch = RanchSession(
            other_bag,
            other_bag.inside,
            destination(35),
            lease=other_generation,
            now_ms=2000,
        )
        other_ranch.move(
            other_ranch.inside,
            {"x": first[1][0], "y": first[1][1], "z": first[1][2]},
        )
        from wakfu_server.profession_store import ensure_learned
        from wakfu_server.inventory_items import grant

        ensure_learned(
            self.store, other_account, other_generation, other_character["id"], [72]
        )
        other_seed = grant(
            self.store,
            other_account,
            other_generation,
            other_character["id"],
            reference=4275,
            quantity=1,
            container=other_character["inventory_containers"][0]["uid"],
            slot=0,
            allowed_references={4275},
        )
        other_runtime = type(self.runtime)(
            self.store,
            growth_seconds=30,
            probability_context=self.runtime.probability_context,
            location_context=lambda stored: self.garden(
                stored, [other_ranch.inside], store=self.store
            ),
        )
        other_target = first[0]
        other_runtime.begin(
            other_account,
            other_generation,
            other_ranch.inside,
            struct.pack(
                ">iqii",
                self.seed["action_id"],
                other_seed["uid"],
                other_target[0],
                other_target[1],
            ),
            lambda current, request, seed, resource: self.authorize_garden(
                self.store, current, request, seed, resource
            ),
        )
        self.now[0] += 3
        other_runtime.complete(
            other_account, other_generation, other_ranch.inside, b"\x02\x00\x02"
        )
        self.assertEqual(
            self._resource_rows(other_ranch.inside["instance_id"]), [other_target]
        )
        self.assertEqual(
            self._component18_biomes(
                haven_ranch_building_knowledge.packet(self.store, other_account)
            ),
            {},
        )

    def test_deployed_native_creatures_block_exact_owned_occupancy_only(self):
        from wakfu_server import haven_ranch_building_knowledge, haven_ranch_buildings
        from wakfu_server import haven_ranch_furniture, haven_ranch_herd
        from wakfu_server.haven_bag import HavenBagSession
        from wakfu_server.haven_ranch import RanchSession, destination
        from wakfu_server.inventory_items import grant
        from wakfu_server.combat_terrain import map_geometry
        from wakfu_server.ranch_native_paddocks import enclosed_regions

        geometry = map_geometry(1440)
        target_xy = (5, 5)

        def create_scene(label):
            account = self.store.register(label, "password-test")["id"]
            char = self.store.create_character(account, label)
            generation = self.store.begin_session(account)
            char = self.store.select_character(account, generation, char["id"])
            bag = HavenBagSession(char)
            session = RanchSession(
                bag,
                bag.inside,
                destination(35),
                lease=generation,
                now_ms=1000,
            )
            return account, generation, char, session

        def add_source(account, generation, char, reference):
            with self.store.connection() as db:
                container = db.execute(
                    "SELECT uid FROM inventory_containers WHERE character_id=%s "
                    "AND kind=0 ORDER BY uid LIMIT 1",
                    (char["id"],),
                ).fetchone()
            self.assertIsNotNone(container)
            return grant(
                self.store,
                account,
                generation,
                char["id"],
                reference=reference,
                quantity=1,
                container=container["uid"],
                slot=10 + reference % 10,
                allowed_references={reference},
            )

        def learn_fence_plan(account, generation, char):
            source = add_source(account, generation, char, 33111)
            result = haven_ranch_building_knowledge.learn(
                self.store,
                account,
                generation,
                char["id"],
                struct.pack(">iq", 15153, source["uid"]),
            )
            self.assertTrue(result["applied"])

        def build_enclosure(account, generation, char, session):
            learn_fence_plan(account, generation, char)
            for x in range(4, 9):
                for y in range(4, 9):
                    if x not in (4, 8) and y not in (4, 8):
                        continue
                    result = haven_ranch_buildings.operate(
                        self.store,
                        account,
                        generation,
                        session.inside,
                        12671,
                        struct.pack(">iBiii", 6, 1, 85, x, y),
                        session=session,
                    )
                    self.assertTrue(result["changed"])
            with self.store.connection() as db:
                rows = haven_ranch_buildings.rows(db, account, 1)
            regions = enclosed_regions(1, 1, rows)
            self.assertTrue(any((6, 6) in region["interior"] for region in regions))

        def acquire_creature(account, generation, char):
            actions, _definitions = haven_ranch_herd.catalog()
            action_id, action = sorted(actions.items())[0]
            source = add_source(account, generation, char, action["item_ref"])
            result = haven_ranch_herd.use(
                self.store,
                account,
                generation,
                char["id"],
                struct.pack(">iq", action_id, source["uid"]),
            )
            self.assertEqual(result["consumed"], 1)
            self.assertTrue(result["creature"]["native_tJT"])
            return result["creature"]["uid"]

        def deploy_creature(account, generation, char, session, uid, *, x=6, y=6):
            result = haven_ranch_herd.deploy(
                self.store,
                account,
                generation,
                session.inside,
                struct.pack(">qii", uid, x, y),
                session=session,
                geometry=geometry,
            )
            self.assertFalse(result["creature"]["native_tJT"])
            self.assertEqual(
                (
                    result["creature"]["native_eqf"],
                    result["creature"]["x"],
                    result["creature"]["y"],
                ),
                (1, x, y),
            )
            return result

        # A distinct account's deployed animal at the same map cell must not
        # enter this account's exact-cell occupancy query.
        (
            foreign_account,
            foreign_generation,
            foreign_char,
            foreign_session,
        ) = create_scene("ranch-foreign-creature")
        build_enclosure(
            foreign_account, foreign_generation, foreign_char, foreign_session
        )
        foreign_uid = acquire_creature(
            foreign_account, foreign_generation, foreign_char
        )
        deploy_creature(
            foreign_account,
            foreign_generation,
            foreign_char,
            foreign_session,
            foreign_uid,
            x=target_xy[0],
            y=target_xy[1],
        )
        foreign_independent = self._place((target_xy[0], target_xy[1], 0))
        self.assertTrue(foreign_independent["changed"])
        host_building_uid = foreign_independent["building"]["uid"]
        haven_ranch_buildings.operate(
            self.store,
            self.account,
            self.generation,
            self.ranch.inside,
            13480,
            struct.pack(">q", host_building_uid),
            session=self.ranch,
        )

        # Create the host's own actual group-1 enclosure. Select an interior
        # cell that is also an original planting surface and walkable height.
        build_enclosure(self.account, self.generation, self.character, self.ranch)
        # Simulate a pre-migration fence set with no durable fBS projection.
        # The next real scene snapshot must reconstruct the paddock from the
        # persisted native fences before either fBQ deployment or publication.
        with self.store.connection() as db:
            db.execute(
                "DELETE FROM account_ranch_paddocks WHERE account_id=%s",
                (self.account,),
            )
        entry_snapshot = haven_ranch_furniture.snapshot(
            self.store,
            self.account,
            self.generation,
            self.ranch.inside,
            session=self.ranch,
            now_ms=int(self.store.now().timestamp() * 1000),
        )
        self.assertEqual(entry_snapshot["packet"][0], 13864)
        with self.store.connection() as db:
            reconstructed_paddocks = haven_ranch_herd.paddocks(db, self.account, 1)
        self.assertEqual(len(reconstructed_paddocks), 1)
        self.assertIn([5, 5], reconstructed_paddocks[0]["interior"])
        target, edge = next(
            ((x, y, z), start)
            for x, y in ((x, y) for x in range(5, 8) for y in range(5, 8))
            for surface in self.private_surfaces(1440, x, y)
            for z in (surface["z"],)
            for start, end in self.edges
            if end[:2] == (x, y)
            and end[2] == z
            and any(cell[:2] == [x, y] and cell[2] == z for cell in geometry["cells"])
        )
        self.assertEqual(target[:2], target_xy)
        self._plant(target, edge, item_uid=self.seed_item["uid"])
        host_uid = acquire_creature(self.account, self.generation, self.character)
        deploy_creature(
            self.account,
            self.generation,
            self.character,
            self.ranch,
            host_uid,
            x=target_xy[0],
            y=target_xy[1],
        )

        # Completion is revalidated after the animal arrives; preparation is
        # also rejected immediately once its exact original fBQ anchor is live.
        self.now[0] += 3
        with self.assertRaisesRegex(ValueError, "contains a deployed Ranch creature"):
            self.runtime.complete(
                self.account, self.generation, self.ranch.inside, b"\x02\x00\x02"
            )
        self.runtime.cancel(self.character["id"], self.generation)
        self.assertEqual(self._seed_quantity(), 3)
        with self.assertRaisesRegex(ValueError, "overlaps an existing object"):
            self._place(target)

        grant(
            self.store,
            self.account,
            self.generation,
            self.character["id"],
            reference=6293,
            quantity=1,
            container=self.character["inventory_containers"][0]["uid"],
            slot=3,
            allowed_references={6293},
        )
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO account_furniture_knowledge(account_id,item_ref) "
                "VALUES(%s,6293) ON CONFLICT DO NOTHING",
                (self.account,),
            )
        with self.assertRaisesRegex(ValueError, "overlaps a deployed creature"):
            haven_ranch_furniture.deploy(
                self.store,
                self.account,
                self.generation,
                self.ranch.inside,
                struct.pack(">iiii", 6293, 2, target[0], target[1]),
                session=self.ranch,
                geometry=geometry,
            )
        with self.assertRaisesRegex(ValueError, "contains a deployed Ranch creature"):
            self._plant(target, edge, item_uid=self.seed_item["uid"])
        self.assertEqual(self._seed_quantity(), 3)

        # Native rename, repack, and redeploy retain one physical fBQ UID.
        renamed = haven_ranch_herd.rename(
            self.store,
            self.account,
            self.generation,
            self.character["id"],
            struct.pack(">qB", host_uid, 4) + b"Mira",
        )
        self.assertEqual(renamed["creature"]["uid"], host_uid)
        with self.store.connection() as db:
            paddock_uids = [
                row["uid"] for row in haven_ranch_herd.paddocks(db, self.account, 1)
            ]
            deployed = haven_ranch_herd.records(
                db,
                self.account,
                biome_id=1,
                sector_id=1,
                deployed=True,
            )
        self.assertEqual(len(paddock_uids), 1)
        self.assertEqual(len(deployed), 1)
        self.assertEqual(deployed[0]["uid"], host_uid)
        self.assertEqual(deployed[0]["native_tJU"], paddock_uids[0])
        self.assertEqual(deployed[0]["name"], "Mira")
        self._assert_component18_matches_scene(self.store, None)

        repacked = haven_ranch_herd.repack(
            self.store,
            self.account,
            self.generation,
            self.ranch.inside,
            struct.pack(">q", host_uid),
            session=self.ranch,
        )
        self.assertTrue(repacked["applied"])
        self.assertEqual(repacked["creature"]["uid"], host_uid)
        with self.store.connection() as db:
            stored = haven_ranch_herd.records(db, self.account)
        self.assertEqual([row["uid"] for row in stored], [host_uid])
        redeployed = deploy_creature(
            self.account, self.generation, self.character, self.ranch, host_uid
        )
        self.assertTrue(redeployed["applied"])
        fixed_now = self.store.now()
        self.store.now = lambda offset_seconds=0: fixed_now + timedelta(
            seconds=offset_seconds
        )
        self._assert_component18_matches_scene(self.store, None)

        reloaded = self.reopen()
        reloaded.now = lambda offset_seconds=0: fixed_now + timedelta(
            seconds=offset_seconds
        )
        with reloaded.connection() as db:
            reopened_creatures = haven_ranch_herd.records(
                db,
                self.account,
                biome_id=1,
                sector_id=1,
                deployed=True,
            )
            reopened_paddocks = haven_ranch_herd.paddocks(db, self.account, 1)
        self.assertEqual([row["uid"] for row in reopened_creatures], [host_uid])
        self.assertEqual([row["uid"] for row in reopened_paddocks], paddock_uids)
        self._assert_component18_matches_scene(reloaded, None)
        scene = haven_ranch_building_knowledge.scene_packet(
            reloaded,
            self.account,
            biome_id=1,
        )
        snapshot = haven_ranch_furniture.snapshot(
            reloaded,
            self.account,
            self.generation,
            self.ranch.inside,
            session=self.ranch,
            now_ms=int(fixed_now.timestamp() * 1000),
        )
        self.assertEqual(snapshot["packet"], scene)

    def test_native_release_preserves_history_frees_capacity_and_removes_deployed_scene_uid(
        self,
    ):
        from psycopg.types.json import Jsonb
        from wakfu_server import haven_ranch_herd, haven_ranch_buildings
        from wakfu_server.haven_ranch_herd_wire import account_animals
        from wakfu_server.inventory_items import grant
        from wakfu_server.inventory_uids import allocate
        from wakfu_server.combat_terrain import map_geometry

        actions, _definitions = haven_ranch_herd.catalog()
        action_id, action = sorted(actions.items())[0]
        source = grant(
            self.store,
            self.account,
            self.generation,
            self.character["id"],
            reference=action["item_ref"],
            quantity=3,
            container=self.character["inventory_containers"][0]["uid"],
            slot=3,
            allowed_references={action["item_ref"]},
        )

        # Build a real native enclosed paddock for the deployed-release half.
        fence = grant(
            self.store,
            self.account,
            self.generation,
            self.character["id"],
            reference=33111,
            quantity=1,
            container=self.character["inventory_containers"][0]["uid"],
            slot=4,
            allowed_references={33111},
        )
        learned = __import__(
            "wakfu_server.haven_ranch_building_knowledge", fromlist=["learn"]
        ).learn(
            self.store,
            self.account,
            self.generation,
            self.character["id"],
            struct.pack(">iq", 15153, fence["uid"]),
        )
        self.assertTrue(learned["applied"])
        for x in range(4, 9):
            for y in range(4, 9):
                if x in (4, 8) or y in (4, 8):
                    placed = haven_ranch_buildings.operate(
                        self.store,
                        self.account,
                        self.generation,
                        self.ranch.inside,
                        12671,
                        struct.pack(">iBiii", 6, 1, 85, x, y),
                        session=self.ranch,
                    )
                    self.assertTrue(placed["changed"])

        def acquire():
            return haven_ranch_herd.use(
                self.store,
                self.account,
                self.generation,
                self.character["id"],
                struct.pack(">iq", action_id, source["uid"]),
            )

        def source_quantity():
            with self.store.connection() as db:
                row = db.execute(
                    "SELECT quantity FROM inventory_items WHERE uid=%s",
                    (source["uid"],),
                ).fetchone()
            return None if row is None else row["quantity"]

        inventory_instance = acquire()["creature"]
        inventory_uid = inventory_instance["uid"]
        with self.store.connection() as db:
            # Represent 99 previously owned native instances using the exact
            # production constructor; the next acquired instance fills fxS.gsB.
            for index in range(99):
                uid = allocate(db)
                native, _slot = haven_ranch_herd.generate(
                    action_id,
                    uid,
                    int(self.store.now().timestamp() * 1000),
                    f"{index + 1:032x}",
                )
                db.execute(
                    "INSERT INTO account_ranch_creatures"
                    "(uid,account_id,definition,birth_ms,attributes,name,scale,inventory) "
                    "VALUES(%s,%s,%s,%s,%s,%s,%s,TRUE)",
                    (
                        uid,
                        self.account,
                        native["definition"],
                        native["birth_ms"],
                        Jsonb(native["attributes"]),
                        native["name"],
                        native["scale"],
                    ),
                )
        with self.assertRaisesRegex(ValueError, "inventory is full"):
            acquire()
        self.assertEqual(source_quantity(), 2)

        body = struct.pack(">q", inventory_uid)
        released_inventory = haven_ranch_herd.release(
            self.store,
            self.account,
            self.generation,
            self.ranch.inside,
            body,
            session=self.ranch,
        )
        self.assertTrue(released_inventory["applied"])
        self.assertIsNone(released_inventory["scene_scope"])
        self.assertFalse(released_inventory["refresh_scene"])
        self.assertEqual(released_inventory["packets"][0][0], 13754)
        self.assertEqual(
            source_quantity(), 2, "release must not refund the consumed source"
        )
        with self.store.connection() as db:
            historical = db.execute(
                "SELECT a.source_uid,a.creature_uid,c.released_at,c.released_by_character_id,c.revision "
                "FROM ranch_creature_acquisitions a JOIN account_ranch_creatures c "
                "ON c.uid=a.creature_uid "
                "WHERE a.creature_uid=%s",
                (inventory_uid,),
            ).fetchone()
        self.assertEqual(historical["source_uid"], source["uid"])
        self.assertEqual(historical["creature_uid"], inventory_uid)
        self.assertIsNotNone(historical["released_at"])
        first_revision = historical["revision"]
        replay_inventory = haven_ranch_herd.release(
            self.store,
            self.account,
            self.generation,
            self.ranch.inside,
            body,
            session=self.ranch,
        )
        self.assertFalse(replay_inventory["applied"])
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT revision FROM account_ranch_creatures WHERE uid=%s",
                    (inventory_uid,),
                ).fetchone()["revision"],
                first_revision,
            )
        with self.store.connection() as db:
            self.assertEqual(len(haven_ranch_herd.records(db, self.account)), 99)

        # Releasing that exact active UID frees one owned slot; a fresh native
        # acquisition succeeds, then is deployed and released from the scene.
        deployed_instance = acquire()["creature"]
        deployed_uid = deployed_instance["uid"]
        self.assertEqual(source_quantity(), 1)
        geometry = map_geometry(1440)
        creature = haven_ranch_herd.deploy(
            self.store,
            self.account,
            self.generation,
            self.ranch.inside,
            struct.pack(">qii", deployed_uid, 6, 6),
            session=self.ranch,
            geometry=geometry,
        )["creature"]
        self.assertFalse(creature["native_tJT"])
        released_scene = haven_ranch_herd.release(
            self.store,
            self.account,
            self.generation,
            self.ranch.inside,
            struct.pack(">q", deployed_uid),
            session=self.ranch,
        )
        self.assertTrue(released_scene["applied"])
        self.assertEqual(released_scene["scene_scope"], (1440, self.character["id"]))
        self.assertTrue(released_scene["refresh_scene"])
        self.assertEqual(released_scene["packets"][0][0], 13754)
        with self.store.connection() as db:
            acquisition_count = db.execute(
                "SELECT count(*) AS count FROM ranch_creature_acquisitions WHERE account_id=%s",
                (self.account,),
            ).fetchone()["count"]
            active = haven_ranch_herd.records(db, self.account)
            scene_records = haven_ranch_herd.records(
                db,
                self.account,
                biome_id=1,
                sector_id=1,
                deployed=True,
            )
            paddocks = haven_ranch_herd.paddocks(db, self.account, 1)
        self.assertEqual(acquisition_count, 2)
        self.assertEqual(len(active), 99)
        self.assertEqual(scene_records, [])
        self.assertEqual(
            len(paddocks), 1, "release retires the animal, not its native fences"
        )
        self.assertEqual(source_quantity(), 1)
        self._assert_component18_matches_scene(self.store, None)
        scene = __import__(
            "wakfu_server.haven_ranch_building_knowledge", fromlist=["scene_packet"]
        ).scene_packet(
            self.store,
            self.account,
            biome_id=1,
        )
        snapshot = __import__(
            "wakfu_server.haven_ranch_furniture", fromlist=["snapshot"]
        ).snapshot(
            self.store,
            self.account,
            self.generation,
            self.ranch.inside,
            session=self.ranch,
            now_ms=int(self.store.now().timestamp() * 1000),
        )
        self.assertEqual(snapshot["packet"], scene)
        replay_scene = haven_ranch_herd.release(
            self.store,
            self.account,
            self.generation,
            self.ranch.inside,
            struct.pack(">q", deployed_uid),
            session=self.ranch,
        )
        self.assertFalse(replay_scene["applied"])
        self.assertTrue(replay_scene["refresh_scene"])

        # Foreign owner and invalid scene attempts cannot mutate tombstones or
        # another account's inventory. Stale generation and combat are covered
        # at the actual World dispatch boundary.
        foreign = self.store.register("ranch-release-foreign", "password-test")["id"]
        foreign_character = self.store.create_character(
            foreign, "Ranch Release Foreign"
        )
        foreign_generation = self.store.begin_session(foreign)
        foreign_character = self.store.select_character(
            foreign,
            foreign_generation,
            foreign_character["id"],
        )
        from wakfu_server.haven_bag import HavenBagSession
        from wakfu_server.haven_ranch import RanchSession, destination

        foreign_bag = HavenBagSession(foreign_character)
        foreign_ranch = RanchSession(
            foreign_bag,
            foreign_bag.inside,
            destination(35),
            lease=foreign_generation,
            now_ms=1000,
        )
        with self.assertRaisesRegex(ValueError, "unavailable or foreign"):
            haven_ranch_herd.release(
                self.store,
                foreign,
                foreign_generation,
                foreign_ranch.inside,
                struct.pack(">q", deployed_uid),
                session=foreign_ranch,
            )
        with self.assertRaisesRegex(ValueError, "installed owned Ranch scene"):
            haven_ranch_herd.release(
                self.store,
                self.account,
                self.generation,
                self.character,
                struct.pack(">q", inventory_uid),
                session=self.ranch,
            )
        self.assertEqual(source_quantity(), 1)
        stale_generation = self.generation
        self.store.begin_session(self.account)
        with self.assertRaisesRegex(ValueError, "Sesión o personaje inválidos"):
            haven_ranch_herd.release(
                self.store,
                self.account,
                stale_generation,
                self.ranch.inside,
                struct.pack(">q", deployed_uid),
                session=self.ranch,
            )
        with self.store.connection() as db:
            self.assertIsNotNone(
                db.execute(
                    "SELECT released_at FROM account_ranch_creatures WHERE uid=%s",
                    (deployed_uid,),
                ).fetchone()["released_at"]
            )

    def _building_rows(self, account):
        with self.store.connection() as db:
            return [
                dict(row)
                for row in db.execute(
                    "SELECT uid,building_ref,x,y,sector_id FROM account_ranch_buildings "
                    "WHERE account_id=%s ORDER BY uid",
                    (account,),
                )
            ]

    def _resource_rows(self, instance_id):
        with self.store.connection() as db:
            return [
                tuple(row[key] for key in ("x", "y", "z"))
                for row in db.execute(
                    "SELECT x,y,z FROM planted_resources WHERE map_id=1440 AND instance_id=%s "
                    "ORDER BY x,y",
                    (instance_id,),
                )
            ]

    @staticmethod
    def _component18_biomes(packet):
        if packet[0] != 13873:
            raise AssertionError("Unexpected native Ranch library opcode")
        body = packet[1]
        if struct.unpack_from(">II", body) != (1, 18):
            raise AssertionError("Unexpected native Ranch component identity")
        sections = []
        cursor = 8
        for _ in range(3):
            length = struct.unpack_from(">I", body, cursor)[0]
            cursor += 4
            sections.append(body[cursor : cursor + length])
            cursor += length
        if cursor != len(body):
            raise AssertionError("Trailing bytes in native Ranch component")
        payload = sections[1]
        count = struct.unpack_from(">h", payload)[0]
        cursor = 2
        result = {}
        for index in range(count):
            biome_id = struct.unpack_from(">i", payload, cursor)[0]
            cursor += 4
            if biome_id in result or index != count - 1:
                raise AssertionError("Malformed native Ranch biome projection")
            result[biome_id] = payload[cursor:]
            cursor = len(payload)
        if cursor != len(payload):
            raise AssertionError("Trailing bytes in native Ranch biome section")
        return result

    def _assert_component18_matches_scene(self, store, building_uid):
        from wakfu_server import haven_ranch_bridges, haven_ranch_building_knowledge
        from wakfu_server import haven_ranch_furniture, haven_ranch_herd
        from wakfu_server.haven_ranch_building_wire import building_record
        from wakfu_server.haven_ranch_furniture_wire import context
        from wakfu_server.haven_ranch_herd_wire import account_animals
        from wakfu_server.ranch_native_geometry import account_buildings_by_sector

        now_ms = int(store.now().timestamp() * 1000)
        actual = self._component18_biomes(
            haven_ranch_building_knowledge.packet(store, self.account)
        )
        with store.connection() as db:
            bag = db.execute(
                "SELECT character_id FROM account_haven_bags WHERE account_id=%s",
                (self.account,),
            ).fetchone()
            sectors = [
                row["sector_id"]
                for row in db.execute(
                    "SELECT sector_id FROM account_ranch_sectors WHERE account_id=%s "
                    "AND biome_id=1 ORDER BY sector_id",
                    (self.account,),
                )
            ]
            self.assertIsNotNone(bag)
            items = haven_ranch_furniture._rows(db, bag["character_id"])
            building_states = haven_ranch_bridges.snapshot(db, bag["character_id"])
            buildings = account_buildings_by_sector(db, self.account, 1)
            creatures, paddocks = haven_ranch_building_knowledge.herd_sectors(
                db,
                self.account,
                1,
                sectors,
            )
            owned_creatures = haven_ranch_herd.records(db, self.account)
            opcode, scene = context(
                self.account,
                1440,
                sectors,
                items,
                now_ms,
                building_states=building_states,
                buildings_by_sector=buildings,
                creatures_by_sector=creatures,
                paddocks_by_sector=paddocks,
            )
            row = (
                None
                if building_uid is None
                else next(
                    dict(source)
                    for source in db.execute(
                        "SELECT * FROM account_ranch_buildings WHERE account_id=%s AND uid=%s",
                        (self.account, building_uid),
                    )
                )
            )
        self.assertEqual(opcode, 13864)
        self.assertEqual(actual, {1: scene[17:]})
        if row is not None:
            self.assertIn(building_record(row), actual[1])
        packet = haven_ranch_building_knowledge.packet(store, self.account)
        body = packet[1]
        cursor = 8
        animals_size = struct.unpack_from(">I", body, cursor)[0]
        cursor += 4
        animals = body[cursor : cursor + animals_size]
        cursor += animals_size
        self.assertEqual(struct.unpack_from(">I", animals)[0], len(owned_creatures))
        encoded_animals = account_animals(owned_creatures)
        self.assertEqual(animals, encoded_animals)
