"""Native bridge costs, persistent private ownership and exact-once activation."""
import struct
import unittest
from unittest.mock import patch

from postgres_case import PostgresCase
from wakfu_server import haven_ranch_bridges as bridges
from wakfu_server.haven_bag import HavenBagSession
from wakfu_server.haven_ranch import RanchSession
from wakfu_server import world_static


class RanchBridgeWireTests(unittest.TestCase):
    def test_original_state_wire_is_owner_slot_boolean(self):
        self.assertEqual(
            bridges.state_packet(7, 2, True), (13080, struct.pack(">qiB", 7, 2, 1))
        )
        self.assertEqual(
            bridges.state_packet(7, 2, False), (13080, struct.pack(">qiB", 7, 2, 0))
        )
        for owner, slot, value in ((0, 2, True), (7, 0, True), (7, 2, 1)):
            with self.assertRaises(ValueError):
                bridges.state_packet(owner, slot, value)


class RanchBridgePersistenceTests(PostgresCase):
    def setUp(self):
        super().setUp()
        self.account = self.store.register("native-bridge-owner", "test-password")["id"]
        self.character = self.store.create_character(self.account, "Bridge owner")
        self.generation = self.store.begin_session(self.account)
        self.character = self.store.select_character(
            self.account, self.generation, self.character["id"]
        )
        self.bag, self.ranch = self.scenes(self.character, self.generation)
        self.container = self.character["inventory_containers"][0]["uid"]
        self.objects = [
            dict(
                id=36068,
                type="GenericActivableInteractiveElement",
                map_id=1440,
                x=-6,
                y=8,
                z=0,
            ),
            dict(
                id=36069,
                type="GenericActivableInteractiveElement",
                map_id=1440,
                x=8,
                y=-8,
                z=0,
            ),
        ]
        native = patch.object(world_static, "objects", return_value=self.objects)
        native.start()
        self.addCleanup(native.stop)

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
            dict(biome_id=1, map_id=1440, x=8, y=-7, z=0),
            lease=generation,
            now_ms=1000,
        )
        return bag, ranch

    def grant(self, ref=33215, quantity=2, slot=0):
        from wakfu_server.inventory_items import grant

        return grant(
            self.store,
            self.account,
            self.generation,
            self.character["id"],
            reference=ref,
            quantity=quantity,
            container=self.container,
            slot=slot,
            allowed_references={ref},
        )

    def activate(
        self,
        *,
        store=None,
        character=None,
        session=None,
        generation=None,
        body=None,
        account=None
    ):
        return bridges.activate(
            store or self.store,
            account or self.account,
            generation or self.generation,
            character or self.ranch.inside,
            (body if body is not None else struct.pack(">qHH", 36069, 0, 0)),
            session=session or self.ranch,
        )

    def states(self):
        with self.store.connection() as db:
            return bridges.snapshot(db, self.ranch.inside["instance_id"])

    def quantity(self, uid):
        with self.store.connection() as db:
            row = db.execute(
                "SELECT quantity FROM inventory_items WHERE uid=%s", (uid,)
            ).fetchone()
            return row["quantity"] if row else 0

    def test_sector_two_consumes_one_then_replays_reconnects_and_owned_hero_without_extra_cost(
        self,
    ):
        source = self.grant()
        self.assertEqual(self.states(), [dict(slot_id=i, state=0) for i in range(1, 5)])
        with self.store.connection() as db:
            self.assertEqual(
                len(bridges.blocked_cells(db, self.ranch.inside["instance_id"])), 12
            )
        result = self.activate()
        with self.store.connection() as db:
            blocked = bridges.blocked_cells(db, self.ranch.inside["instance_id"])
        self.assertEqual(len(blocked), 9)
        self.assertNotIn((9, -10), blocked)
        self.assertIn((-8, 9), blocked)
        self.assertTrue(result["applied"])
        self.assertEqual(self.quantity(source["uid"]), 1)
        self.assertEqual(
            result["private_packets"], [(12470, struct.pack(">qh", source["uid"], -1))]
        )
        self.assertEqual(
            result["scene_packets"], [(13080, struct.pack(">qiB", 1440, 2, 1))]
        )
        self.assertEqual([r["state"] for r in result["states"]], [0, 1, 0, 0])
        replay = self.activate(store=self.reopen())
        self.assertFalse(replay["applied"])
        self.assertFalse(replay["private_packets"])
        self.assertEqual(self.quantity(source["uid"]), 1)
        hero = self.store.create_character(self.account, "Bridge hero")
        hero = self.store.select_character(self.account, self.generation, hero["id"])
        _, ranch = self.scenes(hero, self.generation)
        replay = self.activate(character=ranch.inside, session=ranch)
        self.assertFalse(replay["applied"])
        self.assertEqual([r["state"] for r in replay["states"]], [0, 1, 0, 0])
        self.assertEqual(self.quantity(source["uid"]), 1)
        with self.store.connection() as db:
            rows = list(db.execute("SELECT * FROM haven_ranch_bridges"))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["consumed_uid"], source["uid"])

    def test_sector_one_deletes_exact_single_unit_and_missing_item_cannot_build(self):
        with self.assertRaisesRegex(ValueError, "Missing native bridge"):
            self.activate()
        self.assertTrue(all(row["state"] == 0 for row in self.states()))
        source = self.grant(ref=32883, quantity=1)
        near = dict(self.ranch.inside, x=-6, y=9)
        result = self.activate(character=near, body=struct.pack(">qHH", 36068, 0, 0))
        self.assertTrue(result["applied"])
        self.assertEqual(self.quantity(source["uid"]), 0)
        self.assertEqual([row["state"] for row in self.states()], [1, 0, 0, 0])
        self.assertFalse(
            self.activate(character=near, body=struct.pack(">qHH", 36068, 0, 0))[
                "applied"
            ]
        )

    def test_guest_foreign_instance_out_of_range_and_stale_actor_do_not_consume(self):
        source = self.grant()
        foreign_account = self.store.register("native-bridge-guest", "test-password")[
            "id"
        ]
        guest = self.store.create_character(foreign_account, "Bridge guest")
        lease = self.store.begin_session(foreign_account)
        guest = self.store.select_character(foreign_account, lease, guest["id"])
        _, ranch = self.scenes(guest, lease, self.character)
        with self.assertRaises(ValueError):
            self.activate(
                account=foreign_account,
                generation=lease,
                character=ranch.inside,
                session=ranch,
            )
        for kwargs in (
            {"character": dict(self.ranch.inside, instance_id=999)},
            {"character": dict(self.ranch.inside, x=80)},
            {"character": dict(self.ranch.inside, z=9)},
            {"generation": "expired"},
        ):
            with self.assertRaises(ValueError):
                self.activate(**kwargs)
        self.assertEqual(self.quantity(source["uid"]), 2)
        self.assertTrue(all(row["state"] == 0 for row in self.states()))
        with self.store.connection() as db:
            self.assertEqual(
                bridges.snapshot(db, guest["haven_bag"]["owner_id"]),
                [dict(slot_id=i, state=0) for i in range(1, 5)],
            )

    def test_malformed_unknown_native_identity_and_failed_publication_roll_back_cost_and_state(
        self,
    ):
        source = self.grant()
        for body in (
            b"",
            bytes(11),
            bytes(13),
            struct.pack(">qHH", 36069, 1, 0),
            struct.pack(">qHH", 36069, 0, 1),
            struct.pack(">qHH", 999, 0, 0),
        ):
            with self.assertRaises(ValueError):
                self.activate(body=body)
        self.objects[1]["type"] = "AccountChest"
        with self.assertRaisesRegex(ValueError, "native identity"):
            self.activate()
        self.objects[1]["type"] = "GenericActivableInteractiveElement"
        with patch.object(
            bridges,
            "state_packet",
            side_effect=ValueError("Invalid native publication"),
        ):
            with self.assertRaisesRegex(ValueError, "publication"):
                self.activate()
        self.assertEqual(self.quantity(source["uid"]), 2)
        self.assertTrue(all(row["state"] == 0 for row in self.states()))

    def test_concurrent_native_activations_consume_one_unit_once(self):
        from concurrent.futures import ThreadPoolExecutor

        source = self.grant()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: self.activate(), range(2)))
        self.assertEqual(sorted(result["applied"] for result in results), [False, True])
        self.assertEqual(self.quantity(source["uid"]), 1)
        self.assertEqual(sum(len(result["private_packets"]) for result in results), 1)
        self.assertEqual([row["state"] for row in self.states()], [0, 1, 0, 0])
