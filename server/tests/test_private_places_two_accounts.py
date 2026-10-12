"""Real account custody composed with simultaneous private world membership."""
import struct
import uuid

from postgres_case import PostgresCase
from test_haven_chest import deposit_body
from wakfu_server.haven_bag import HavenBagSession
from wakfu_server.haven_ranch import RanchSession, destination
from wakfu_server.haven_chest import load, transfer, validate_open
from wakfu_server.inventory_items import grant
from wakfu_server.world import World


class TwoAccountPrivatePlaceTests(PostgresCase):
    def setUp(self):
        super().setUp()
        self.accounts = []
        self.characters = []
        self.generations = []
        for label in ("PlaceAlpha", "PlaceBeta"):
            account = self.store.register(label.lower(), "local-test-password")["id"]
            character = self.store.create_character(account, label)
            generation = self.store.begin_session(account)
            self.store.select_character(account, generation, character["id"])
            self.accounts.append(account)
            self.characters.append(self.store.character(account, character["id"]))
            self.generations.append(generation)
        self.bags = [HavenBagSession(character) for character in self.characters]
        self.sent = []
        self.world = World(
            lambda character: character["id"],
            lambda character_id: character_id,
            lambda peer, opcode, body: self.sent.append((peer, opcode, body)),
        )

    def join(self, index, character, *, generation=None, peer=None):
        self.world.join(
            generation or self.generations[index],
            peer or ("peer", index),
            character,
        )

    def assert_only_sender_receives(self, index, character):
        self.sent.clear()
        self.world.broadcast(self.generations[index], character["id"], 777, b"private")
        self.assertEqual(self.sent, [(("peer", index), 777, b"private")])

    def test_simultaneous_bags_ranches_public_visit_and_stale_disconnect(self):
        alpha, beta = self.bags
        self.assertNotEqual(alpha.bag_instance_id, beta.bag_instance_id)
        self.assertEqual(alpha.inside["x"], beta.inside["x"])
        self.assertEqual(alpha.inside["y"], beta.inside["y"])
        for index, bag in enumerate(self.bags):
            self.join(index, bag.inside)
        self.assertEqual(self.sent, [])
        for index, bag in enumerate(self.bags):
            self.assert_only_sender_receives(index, bag.inside)

        ranches = [
            RanchSession(
                bag,
                bag.inside,
                destination(35),
                lease=self.generations[index],
                now_ms=1000,
            )
            for index, bag in enumerate(self.bags)
        ]
        for index, ranch in enumerate(ranches):
            self.world.leave(ranch.inside["id"], self.generations[index])
            self.join(index, ranch.inside)
        self.assertEqual(
            tuple(ranches[0].inside[key] for key in ("map_id", "x", "y", "z")),
            tuple(ranches[1].inside[key] for key in ("map_id", "x", "y", "z")),
        )
        for index, ranch in enumerate(ranches):
            self.assert_only_sender_receives(index, ranch.inside)

        # Alpha intentionally visits Beta's bag, then Beta's ranch. Beta stays
        # in its own live ranch throughout, so sharing is explicit and scoped.
        self.world.leave(self.characters[0]["id"], self.generations[0])
        returned = ranches[0].leave(ranches[0].inside)
        outside = alpha.leave(returned)
        guest_bag = HavenBagSession(outside, owner=self.characters[1])
        self.assertFalse(guest_bag.is_owner)
        self.assertEqual(guest_bag.bag_instance_id, beta.bag_instance_id)
        self.join(0, guest_bag.inside)
        self.assert_only_sender_receives(0, guest_bag.inside)
        guest_ranch = RanchSession(
            guest_bag,
            guest_bag.inside,
            destination(35),
            lease=self.generations[0],
            now_ms=1001,
        )
        self.world.leave(outside["id"], self.generations[0])
        self.sent.clear()
        self.join(0, guest_ranch.inside)
        self.assertEqual(
            set(self.sent),
            {
                (("peer", 0), 12608, self.characters[1]["id"]),
                (("peer", 1), 12608, self.characters[0]["id"]),
            },
        )
        self.sent.clear()
        self.world.broadcast(self.generations[0], outside["id"], 777, b"shared")
        self.assertEqual(
            set(self.sent),
            {(("peer", 0), 777, b"shared"), (("peer", 1), 777, b"shared")},
        )

        self.assertTrue(self.world.leave(outside["id"], self.generations[0]))
        guest_return = guest_ranch.leave(guest_ranch.inside)
        self.assertEqual(guest_bag.leave(guest_return), outside)
        self.assertIn(self.characters[1]["id"], self.world.players)
        self.join(0, alpha.inside, generation="replacement", peer="replacement-peer")
        self.assertFalse(self.world.leave(outside["id"], self.generations[0]))
        self.assertEqual(self.world.players[outside["id"]][0], "replacement")
        self.assertEqual(
            self.world.players[self.characters[1]["id"]][0], self.generations[1]
        )
        self.assertFalse(
            self.world.send_to(outside["id"], self.generations[0], 777, b"stale")
        )

    def test_real_account_chests_remain_distinct_during_public_visit(self):
        chests = []
        for index, character in enumerate(self.characters):
            account, generation = self.accounts[index], self.generations[index]
            chest = load(self.store, account, generation, character["id"])
            item = grant(
                self.store,
                account,
                generation,
                character["id"],
                reference=2504,
                quantity=index + 3,
                container=character["inventory_containers"][0]["uid"],
                slot=0,
                allowed_references={2504},
            )
            transferred = transfer(
                self.store,
                account,
                generation,
                character["id"],
                12038,
                deposit_body(item["uid"], item["quantity"], compartment=chest["id"]),
                opening_token=uuid.uuid4(),
                location=self.bags[index].inside,
            )
            chests.append(transferred["chest"])
        self.assertNotEqual(chests[0]["id"], chests[1]["id"])
        self.assertNotEqual(chests[0]["items"], chests[1]["items"])
        guest = HavenBagSession(self.characters[0], owner=self.characters[1])
        position = guest.move(guest.inside, dict(x=0, y=0, z=0))
        with self.assertRaisesRegex(ValueError, "owner"):
            validate_open(
                position,
                guest,
                struct.pack(">qHH", 99001, 12, 0),
                [dict(id=99001, type="AccountChest", map_id=9, x=0, y=0, z=0)],
                fight_active=False,
            )
        for index, character in enumerate(self.characters):
            actual = load(
                self.store,
                self.accounts[index],
                self.generations[index],
                character["id"],
            )
            self.assertEqual(actual["items"], chests[index]["items"])
