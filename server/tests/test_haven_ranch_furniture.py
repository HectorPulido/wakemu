"""Transactional Ranch library placement, distinct from bag/inventory custody."""
import struct
from unittest.mock import patch

from postgres_case import PostgresCase
from wakfu_server.haven_bag import HavenBagSession
from wakfu_server.haven_ranch import RanchSession
from wakfu_server import haven_ranch_furniture as furniture
from wakfu_server import haven_bag_furniture_world as world


class RanchFurniturePersistenceTests(PostgresCase):
    def setUp(self):
        super().setUp()
        self.account = self.store.register("ranch-furniture-owner", "test-password")[
            "id"
        ]
        self.character = self.store.create_character(self.account, "Furniture owner")
        self.generation = self.store.begin_session(self.account)
        self.character = self.store.select_character(
            self.account, self.generation, self.character["id"]
        )
        self.bag, self.ranch = self.scenes(self.character, self.generation)
        self.geometry = dict(
            map_id=1440, cells=[(1, 1, 0), (2, 1, 0), (1, -20, 4), (-20, -5, 0)]
        )
        # Native exported mapping: item6293 -> Decoration2770, criterion absent.
        self.definition = dict(template_id=2770, kind="Decoration")
        self.render = patch.object(world, "resolve_item", return_value=self.definition)
        self.render.start()
        self.addCleanup(self.render.stop)
        from wakfu_server.inventory_items import grant

        grant(
            self.store,
            self.account,
            self.generation,
            self.character["id"],
            reference=6293,
            quantity=3,
            container=self.character["inventory_containers"][0]["uid"],
            slot=0,
            allowed_references={6293},
        )
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO account_furniture_knowledge(account_id,item_ref) VALUES(%s,6293)",
                (self.account,),
            )
        self.before = self.custody()

    @staticmethod
    def scenes(character, generation, owner=None):
        bag = (
            HavenBagSession(character, owner=owner)
            if owner
            else HavenBagSession(character)
        )
        ranch = RanchSession(
            bag,
            bag.inside,
            dict(biome_id=1, map_id=1440, x=1, y=1, z=0),
            lease=generation,
            now_ms=1000,
        )
        return bag, ranch

    def custody(self):
        with self.store.connection() as db:
            return (
                list(
                    db.execute(
                        "SELECT uid,character_id,reference,quantity,container,slot FROM inventory_items ORDER BY uid"
                    )
                ),
                list(
                    db.execute(
                        "SELECT character_id,furniture FROM haven_bags ORDER BY character_id"
                    )
                ),
                list(
                    db.execute(
                        "SELECT * FROM account_furniture_knowledge ORDER BY account_id,item_ref"
                    )
                ),
            )

    def place(
        self, *, x=1, y=1, ref=6293, character=None, session=None, generation=None
    ):
        return furniture.deploy(
            self.store,
            self.account,
            generation or self.generation,
            character or self.ranch.inside,
            struct.pack(">iiii", ref, 2, x, y),
            session=session or self.ranch,
            geometry=self.geometry,
            resolver=lambda _: self.definition,
        )

    def test_place_move_cross_native_areas_reconnect_and_repack_preserves_custody(self):
        placed = self.place()
        uid = placed["item"]["item_uid"]
        self.assertEqual([p[0] for p in placed["packets"]], [12259, 13664])
        self.assertEqual(placed["item"]["area_id"], 1)
        rotated = furniture.edit(
            self.store,
            self.account,
            self.generation,
            self.ranch.inside,
            12870,
            struct.pack(">qHH", uid, 29, 0),
            session=self.ranch,
            geometry=self.geometry,
        )
        self.assertEqual(rotated["item"]["direction"], 3)
        self.assertEqual([p[0] for p in rotated["packets"]], [12452, 13082, 13664])
        moved = furniture.edit(
            self.store,
            self.account,
            self.generation,
            self.ranch.inside,
            12363,
            struct.pack(">qiihi", uid, 1, -20, 4, 6),
            session=self.ranch,
            geometry=self.geometry,
        )
        self.assertEqual(moved["item"]["area_id"], 2)
        self.assertEqual([p[0] for p in moved["packets"]], [12780, 12259, 13082, 13664])
        reopened = self.reopen()
        snapshot = furniture.snapshot(
            reopened,
            self.account,
            self.generation,
            self.ranch.inside,
            session=self.ranch,
            now_ms=2000,
        )
        self.assertEqual(
            [(i["item_uid"], i["x"], i["y"]) for i in snapshot["items"]],
            [(uid, 1, -20)],
        )
        self.assertEqual(snapshot["packet"][0], 13864)
        self.assertEqual([p[0] for p in snapshot["scene_packets"]], [13664])
        packed = furniture.edit(
            reopened,
            self.account,
            self.generation,
            self.ranch.inside,
            12870,
            struct.pack(">qHH", uid, 23, 0),
            session=self.ranch,
            geometry=self.geometry,
        )
        self.assertEqual([p[0] for p in packed["packets"]], [12780, 13082])
        for result in (placed, rotated, moved, packed):
            for opcode, body in result["packets"]:
                if opcode in (12259, 12452, 12780):
                    self.assertEqual(struct.unpack_from(">q", body)[0], 1440)
        self.assertEqual(
            furniture.snapshot(
                reopened,
                self.account,
                self.generation,
                self.ranch.inside,
                session=self.ranch,
                now_ms=3000,
            )["items"],
            [],
        )
        self.assertEqual(self.custody(), self.before)

    def test_guest_can_see_host_furniture_but_cannot_edit_or_forge_owner(self):
        placed = self.place()
        uid = placed["item"]["item_uid"]
        guest_account = self.store.register("ranch-furniture-guest", "test-password")[
            "id"
        ]
        guest = self.store.create_character(guest_account, "Furniture guest")
        lease = self.store.begin_session(guest_account)
        guest = self.store.select_character(guest_account, lease, guest["id"])
        _, ranch = self.scenes(guest, lease, self.character)
        shown = furniture.snapshot(
            self.store, guest_account, lease, ranch.inside, session=ranch, now_ms=2000
        )
        self.assertEqual(shown["items"][0]["item_uid"], uid)
        with self.assertRaises(ValueError):
            furniture.deploy(
                self.store,
                guest_account,
                lease,
                ranch.inside,
                struct.pack(">iiii", 6293, 0, 2, 1),
                session=ranch,
                geometry=self.geometry,
                resolver=lambda _: self.definition,
            )
        with self.assertRaises(ValueError):
            furniture.edit(
                self.store,
                guest_account,
                lease,
                ranch.inside,
                12870,
                struct.pack(">qHH", uid, 23, 0),
                session=ranch,
                geometry=self.geometry,
            )
        _, own_ranch = self.scenes(guest, lease)
        self.assertEqual(
            furniture.snapshot(
                self.store,
                guest_account,
                lease,
                own_ranch.inside,
                session=own_ranch,
                now_ms=2000,
            )["items"],
            [],
        )
        with self.assertRaises(ValueError):
            furniture.edit(
                self.store,
                guest_account,
                lease,
                own_ranch.inside,
                12870,
                struct.pack(">qHH", uid, 23, 0),
                session=own_ranch,
                geometry=self.geometry,
            )

    def test_unknown_criteria_geometry_occupancy_and_stale_lease_fail_without_custody_changes(
        self,
    ):
        with self.assertRaises(ValueError):
            self.place(
                x=25, y=7
            )  # Ranch chest area is outside installed terrain areas.
        with self.assertRaises(ValueError):
            self.place(
                x=4, y=4
            )  # Area membership alone cannot invent a walkable height.
        with self.assertRaises(ValueError):
            self.place(
                ref=4353
            )  # Native reference exists, but account has not learned it.
        with self.assertRaises(ValueError):
            self.place(generation="expired")
        placed = self.place()
        with self.assertRaises(ValueError):
            self.place()  # Occupied cell, without allocating another virtual unit.
        with self.assertRaises(ValueError):
            furniture.edit(
                self.store,
                self.account,
                self.generation,
                self.ranch.inside,
                12363,
                struct.pack(">qiihi", placed["item"]["item_uid"], 2, 1, 9, 0),
                session=self.ranch,
                geometry=self.geometry,
            )
        with self.assertRaises(ValueError):
            furniture.edit(
                self.store,
                self.account,
                self.generation,
                self.ranch.inside,
                12870,
                struct.pack(">qHH", placed["item"]["item_uid"], 23, 1),
                session=self.ranch,
                geometry=self.geometry,
            )
        self.assertEqual(self.custody(), self.before)

    def test_native_building_mask_blocks_later_scene_furniture_placement(self):
        from wakfu_server.ranch_native_geometry import bootstrap_account_sectors
        from wakfu_server.inventory_uids import allocate

        with self.store.connection() as db:
            bootstrap_account_sectors(db, self.account, 1)
            uid = allocate(db)
            db.execute(
                "INSERT INTO account_ranch_buildings "
                "(uid,account_id,biome_id,sector_id,building_ref,mode_id,view_kind,view_value,x,y) "
                "VALUES(%s,%s,1,1,33,1,0,1,1,1)",
                (uid, self.account),
            )
        with self.assertRaisesRegex(ValueError, "overlaps a native building"):
            self.place(x=1, y=1)
        self.assertEqual(self.custody(), self.before)

    def test_owned_hero_shares_account_ranch_and_prohibited_reference_stays_blocked(
        self,
    ):
        placed = self.place()
        hero = self.store.create_character(self.account, "Furniture hero")
        hero = self.store.select_character(self.account, self.generation, hero["id"])
        _, ranch = self.scenes(hero, self.generation)
        self.assertEqual(ranch.inside["instance_id"], self.ranch.inside["instance_id"])
        shown = furniture.snapshot(
            self.store,
            self.account,
            self.generation,
            ranch.inside,
            session=ranch,
            now_ms=2000,
        )
        self.assertEqual(shown["items"][0]["item_uid"], placed["item"]["item_uid"])
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO account_furniture_knowledge(account_id,item_ref) VALUES(%s,27927)",
                (self.account,),
            )
        with self.assertRaisesRegex(
            ValueError, "unsupported native placement criterion"
        ):
            self.place(character=ranch.inside, session=ranch, x=2, ref=27927)
        packed = furniture.edit(
            self.store,
            self.account,
            self.generation,
            ranch.inside,
            12870,
            struct.pack(">qHH", placed["item"]["item_uid"], 23, 0),
            session=ranch,
            geometry=self.geometry,
        )
        self.assertTrue(packed["removed"])
