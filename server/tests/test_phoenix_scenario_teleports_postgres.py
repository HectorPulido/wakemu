"""Persistent native Phoenix binding and scenario travel boundaries."""
import struct

from postgres_case import PostgresCase


class PhoenixScenarioTeleportsPostgresTests(PostgresCase):
    def setUp(self):
        super().setUp()
        self.account = self.store.register("phoenix-owner", "local-password")["id"]
        self.main = self.store.create_character(self.account, "Phoenix Main")
        self.generation = self.store.begin_session(self.account)
        self.store.select_character(self.account, self.generation, self.main["id"])

    def give(self, character_id, reference):
        with self.store.connection() as db:
            bag = db.execute(
                "SELECT uid FROM inventory_containers WHERE character_id=%s AND kind=0",
                (character_id,),
            ).fetchone()["uid"]
            slot = db.execute(
                "SELECT COALESCE(MAX(slot)+1,0) AS slot FROM inventory_items WHERE container=%s",
                (bag,),
            ).fetchone()["slot"]
            return db.execute(
                "INSERT INTO inventory_items(character_id,reference,quantity,container,slot) VALUES(%s,%s,1,%s,%s) RETURNING uid",
                (character_id, reference, bag, slot),
            ).fetchone()["uid"]

    def test_adjacent_native_phoenix_binding_persists_and_encodes_original_section(
        self,
    ):
        from wakfu_server.phoenix_points import points, activate, section
        from wakfu_server.combat_terrain import map_geometry

        point = next(iter(points().values()))
        geometry = map_geometry(point["map_id"])
        origin = (int(point["x"]), int(point["y"]), int(point["z"]))
        cells = {tuple(cell) for cell in geometry["cells"]}
        current = next(
            cell
            for cell in sorted(cells)
            if abs(cell[0] - origin[0]) + abs(cell[1] - origin[1]) <= 1
        )
        with self.store.connection() as db:
            db.execute(
                "UPDATE characters SET map_id=%s,instance_id=0,x=%s,y=%s,z=%s WHERE id=%s",
                (point["map_id"], *current, self.main["id"]),
            )
        before = self.store.character(self.account, self.main["id"])
        body = struct.pack(">qHH", point["id"], 0, 0)
        result = activate(
            self.store,
            self.account,
            self.generation,
            self.main["id"],
            body,
            location=before,
        )
        self.assertTrue(result["applied"])
        reopened = self.reopen().character(self.account, self.main["id"])
        self.assertEqual(point["id"], reopened["saved_phoenix_id"])
        self.assertEqual(struct.pack(">i", point["id"]), section(reopened))
        with self.assertRaises(ValueError):
            activate(
                self.store,
                self.account,
                self.generation,
                self.main["id"],
                struct.pack(">qHH", point["id"], 1, 0),
            )
        with self.assertRaises(ValueError):
            activate(
                self.store,
                self.account,
                self.generation,
                self.main["id"],
                body,
                in_fight=True,
            )
        with self.assertRaises(ValueError):
            activate(
                self.store,
                self.account,
                self.generation,
                self.main["id"],
                body,
                location=dict(before, x=before["x"] + 1),
            )
        with self.store.connection() as db:
            db.execute(
                "UPDATE characters SET x=99,y=99 WHERE id=%s", (self.main["id"],)
            )
        with self.assertRaises(ValueError):
            activate(self.store, self.account, self.generation, self.main["id"], body)
        with self.store.connection() as db:
            db.execute(
                "UPDATE characters SET x=%s,y=%s,instance_id=9 WHERE id=%s",
                (current[0], current[1], self.main["id"]),
            )
        with self.assertRaises(ValueError):
            activate(self.store, self.account, self.generation, self.main["id"], body)
        with self.store.connection() as db:
            db.execute(
                "UPDATE characters SET instance_id=0,hp=0,health_dead=true WHERE id=%s",
                (self.main["id"],),
            )
        with self.assertRaises(ValueError):
            activate(self.store, self.account, self.generation, self.main["id"], body)
        with self.store.connection() as db:
            db.execute(
                "UPDATE characters SET hp=max_hp,health_dead=false WHERE id=%s",
                (self.main["id"],),
            )
        self.assertEqual(
            point["id"],
            self.store.character(self.account, self.main["id"])["saved_phoenix_id"],
        )

    def test_saved_phoenix_scenario_relocates_main_and_active_hero_with_retryable_receipt(
        self,
    ):
        from wakfu_server.characters.heroes import add
        from wakfu_server.phoenix_points import points, activate
        from wakfu_server.item_scenario_teleports import plan
        from wakfu_server.item_teleports import use, pending, acknowledge

        hero = self.store.create_character(self.account, "Phoenix Hero")
        add(self.store, self.account, self.generation, self.main["id"], hero["id"])
        point = next(iter(points().values()))
        from wakfu_server.combat_terrain import map_geometry

        geometry = map_geometry(point["map_id"])
        cells = {tuple(cell) for cell in geometry["cells"]}
        origin = (int(point["x"]), int(point["y"]), int(point["z"]))
        current = next(
            cell
            for cell in sorted(cells)
            if abs(cell[0] - origin[0]) + abs(cell[1] - origin[1]) <= 1
        )
        with self.store.connection() as db:
            db.execute(
                "UPDATE characters SET map_id=%s,instance_id=0,x=%s,y=%s,z=%s WHERE id=%s",
                (point["map_id"], *current, self.main["id"]),
            )
        before = self.store.character(self.account, self.main["id"])
        activate(
            self.store,
            self.account,
            self.generation,
            self.main["id"],
            struct.pack(">qHH", point["id"], 0, 0),
            location=before,
        )
        uid = self.give(self.main["id"], 19022)
        with self.store.connection() as db:
            db.execute(
                "UPDATE characters SET map_id=552,instance_id=0,x=0,y=0,z=0 WHERE id=%s",
                (self.main["id"],),
            )
            db.execute(
                "UPDATE characters SET map_id=552,instance_id=0,x=1,y=0,z=0 WHERE id=%s",
                (hero["id"],),
            )
        result = use(
            self.store,
            None,
            self.account,
            self.generation,
            self.main["id"],
            struct.pack(">iq", 7137, uid),
            in_fight=False,
        )
        destination = result["transition"]["destination"]
        moved_hero = self.store.character(self.account, hero["id"])
        self.assertEqual(
            tuple(destination[key] for key in ("map_id", "instance_id", "x", "y", "z")),
            tuple(moved_hero[key] for key in ("map_id", "instance_id", "x", "y", "z")),
        )
        self.assertEqual(
            result["transition"]["token"],
            pending(self.store, self.account, self.generation, self.main["id"])[
                "transition"
            ]["token"],
        )
        retry = use(
            self.store,
            None,
            self.account,
            self.generation,
            self.main["id"],
            struct.pack(">iq", 7137, uid),
            in_fight=False,
        )
        self.assertFalse(retry["applied"])
        acknowledge(
            self.store,
            self.account,
            self.generation,
            self.main["id"],
            result["transition"]["token"],
        )
        self.assertIsNone(
            pending(self.store, self.account, self.generation, self.main["id"])
        )
        unlinked = self.store.create_character(self.account, "Phoenix Unlinked")
        uid2 = self.give(unlinked["id"], 19022)
        with self.assertRaises(ValueError):
            use(
                self.store,
                None,
                self.account,
                self.generation,
                unlinked["id"],
                struct.pack(">iq", 7137, uid2),
                in_fight=False,
            )

    def test_national_scenario_maps_use_native_walkable_phoenix_and_reject_neutral(
        self,
    ):
        from wakfu_server.item_scenario_teleports import NATION_MAPS, plan
        from wakfu_server.phoenix_points import points
        from wakfu_server.combat_terrain import map_geometry

        for nation, map_id in NATION_MAPS.items():
            character = dict(self.main, nation_id=nation, hp=100, health_dead=False)
            route = plan(10859, character)
            self.assertEqual(map_id, route["destination"]["map_id"])
            cells = {tuple(cell) for cell in map_geometry(map_id)["cells"]}
            self.assertIn(
                tuple(route["destination"][key] for key in ("x", "y", "z")), cells
            )
            self.assertEqual(
                1, len([p for p in points().values() if p["map_id"] == map_id])
            )
        for nation in (0, 34):
            with self.assertRaises(ValueError):
                plan(
                    10859, dict(self.main, nation_id=nation, hp=100, health_dead=False)
                )
        uid = self.give(self.main["id"], 19020)
        with self.assertRaises(ValueError):
            from wakfu_server.item_teleports import use

            use(
                self.store,
                None,
                self.account,
                self.generation,
                self.main["id"],
                struct.pack(">iq", 10859, uid),
                in_fight=False,
            )
        with self.store.connection() as db:
            self.assertEqual(
                1,
                db.execute(
                    "SELECT quantity FROM inventory_items WHERE uid=%s", (uid,)
                ).fetchone()["quantity"],
            )
