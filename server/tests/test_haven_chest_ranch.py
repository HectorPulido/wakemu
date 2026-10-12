"""The same owned account chest is usable inside its authorized ranch child."""
from copy import copy
import struct
import unittest
import uuid

from wakfu_server.haven_bag import HavenBagSession
from wakfu_server.haven_ranch import RanchSession
from wakfu_server.haven_chest import can_access_location, validate_open, load, transfer


def scenes(character, generation):
    bag = HavenBagSession(character)
    ranch = RanchSession(
        bag,
        bag.inside,
        dict(biome_id=1, map_id=1440, x=25, y=8, z=0),
        lease=generation,
        now_ms=1000,
    )
    return bag, ranch


class HavenChestRanchCapabilityTests(unittest.TestCase):
    def setUp(self):
        self.character = dict(
            id=7, account_id=2, map_id=527, instance_id=0, x=1, y=2, z=3
        )
        self.bag, self.ranch = scenes(self.character, "lease")
        self.object = dict(id=36088, type="AccountChest", map_id=1440, x=25, y=7, z=0)
        self.body = struct.pack(">qHH", 36088, 12, 0)

    def test_owned_bag_and_exact_owned_ranch_capability(self):
        self.assertTrue(can_access_location(self.bag.inside, self.bag))
        self.assertFalse(can_access_location(self.ranch.inside, self.bag))
        self.assertTrue(can_access_location(self.ranch.inside, self.bag, self.ranch))
        self.assertEqual(
            validate_open(
                self.ranch.inside,
                self.bag,
                self.body,
                [self.object],
                fight_active=False,
                ranch_session=self.ranch,
            ),
            36088,
        )

    def test_guest_foreign_parent_closed_and_wrong_owner_denied(self):
        other = HavenBagSession(
            dict(self.character, id=8, account_id=3), owner=self.character
        )
        variants = [
            (self.ranch.inside, other, self.ranch),
            (dict(self.ranch.inside, account_id=3), self.bag, self.ranch),
        ]
        child = copy(self.ranch)
        child.parent = other
        variants.append((child.inside, other, child))
        child = copy(self.ranch)
        child.closed = True
        variants.append((child.inside, self.bag, child))
        child = copy(self.ranch)
        child.return_point = dict(child.return_point, instance_id=99)
        variants.append((child.inside, self.bag, child))
        for character, bag, ranch in variants:
            with self.subTest(character=character):
                self.assertFalse(can_access_location(character, bag, ranch))
                with self.assertRaises(ValueError):
                    validate_open(
                        character,
                        bag,
                        self.body,
                        [self.object],
                        fight_active=False,
                        ranch_session=ranch,
                    )

    def test_wrong_native_object_map_rewards_chest_range_and_combat_denied(self):
        for obj, character, fighting in (
            (dict(self.object, map_id=9), self.ranch.inside, False),
            (dict(self.object, type="RanchRewardsChest"), self.ranch.inside, False),
            (self.object, dict(self.ranch.inside, x=99), False),
            (self.object, self.ranch.inside, True),
        ):
            with self.assertRaises(ValueError):
                validate_open(
                    character,
                    self.bag,
                    self.body,
                    [obj],
                    fight_active=fighting,
                    ranch_session=self.ranch,
                )


from postgres_case import PostgresCase
from test_haven_chest import deposit_body, withdraw_body
from wakfu_server.inventory_items import grant


class HavenChestRanchPersistenceTests(PostgresCase):
    def setUp(self):
        super().setUp()
        self.account = self.store.register("ranch-chest", "local-test-password")["id"]
        self.character = self.store.create_character(self.account, "Ranch chest")
        self.generation = self.store.begin_session(self.account)
        self.character = self.store.select_character(
            self.account, self.generation, self.character["id"]
        )
        self.bag, self.ranch = scenes(self.character, self.generation)
        self.chest = load(
            self.store, self.account, self.generation, self.character["id"]
        )
        self.container = self.character["inventory_containers"][0]["uid"]
        self.item = grant(
            self.store,
            self.account,
            self.generation,
            self.character["id"],
            reference=2504,
            quantity=9,
            container=self.container,
            slot=0,
            allowed_references={2504},
        )

    def deposit(self, *, ranch=None, location=None, generation=None):
        return transfer(
            self.store,
            self.account,
            generation or self.generation,
            self.character["id"],
            12038,
            deposit_body(self.item["uid"], 4, compartment=self.chest["id"]),
            opening_token=uuid.uuid4(),
            location=location or self.ranch.inside,
            ranch_session=ranch or self.ranch,
        )

    def test_ranch_deposit_bag_withdraw_same_account_chest_and_custody_receipts(self):
        result = self.deposit()
        self.assertEqual(result["chest"]["id"], self.chest["id"])
        self.assertEqual(result["chest"]["items"][0]["item"]["quantity"], 4)
        result = transfer(
            self.store,
            self.account,
            self.generation,
            self.character["id"],
            12551,
            withdraw_body(
                self.character["id"],
                2504,
                2,
                self.container,
                compartment=self.chest["id"],
            ),
            opening_token=uuid.uuid4(),
            location=self.bag.inside,
        )
        self.assertEqual(result["character"]["inventory_items"][0]["quantity"], 7)
        self.assertEqual(result["chest"]["items"][0]["item"]["quantity"], 2)
        self.assertEqual(
            load(self.store, self.account, self.generation, self.character["id"]),
            result["chest"],
        )
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM account_haven_chest_receipts WHERE account_id=%s",
                    (self.account,),
                ).fetchone()["n"],
                2,
            )

    def test_stale_ranch_lease_and_canonical_bag_instance_denied_without_custody_change(
        self,
    ):
        child = copy(self.ranch)
        child.lease = "stale"
        with self.assertRaises(ValueError):
            self.deposit(ranch=child)
        parent = copy(self.bag)
        parent.bag_instance_id += 100
        child = copy(self.ranch)
        child.parent = parent
        parent.inside = dict(parent.inside, instance_id=parent.bag_instance_id)
        child.return_point = dict(
            child.return_point, instance_id=parent.bag_instance_id
        )
        child.inside = dict(child.inside, instance_id=parent.bag_instance_id)
        self.assertTrue(can_access_location(child.inside, parent, child))
        with self.assertRaises(ValueError):
            self.deposit(ranch=child, location=child.inside)
        current = self.store.character(self.account, self.character["id"])
        self.assertEqual(current["inventory_items"][0]["quantity"], 9)
        self.assertEqual(
            load(self.store, self.account, self.generation, self.character["id"])[
                "items"
            ],
            [],
        )
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM account_haven_chest_receipts WHERE account_id=%s",
                    (self.account,),
                ).fetchone()["n"],
                0,
            )
