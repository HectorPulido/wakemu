"""Account chest ownership fences across real isolated PostgreSQL accounts."""
import struct
import uuid
import unittest

from postgres_case import PostgresCase
from test_haven_chest import deposit_body, withdraw_body
from wakfu_server.haven_chest import load, transfer, validate_open
from wakfu_server.haven_bag import HavenBagSession
from wakfu_server.inventory_items import grant


class HavenChestAccountIsolationTests(PostgresCase):
    def setUp(self):
        super().setUp()
        self.store.clock = lambda: 1000
        self.owner_account = self.store.register(
            "chest-isolation-owner", "local-test-password"
        )["id"]
        self.other_account = self.store.register(
            "chest-isolation-other", "local-test-password"
        )["id"]
        self.owner = self.store.create_character(self.owner_account, "Owner")
        self.sibling = self.store.create_character(self.owner_account, "Sibling")
        self.other = self.store.create_character(self.other_account, "Other")
        self.owner_generation = self.store.begin_session(self.owner_account)
        self.other_generation = self.store.begin_session(self.other_account)
        self.store.select_character(
            self.owner_account, self.owner_generation, self.owner["id"]
        )
        self.owner_chest = load(
            self.store, self.owner_account, self.owner_generation, self.owner["id"]
        )
        self.store.select_character(
            self.owner_account, self.owner_generation, self.sibling["id"]
        )
        self.sibling_chest = load(
            self.store,
            self.owner_account,
            self.owner_generation,
            self.sibling["id"],
        )
        self.store.select_character(
            self.owner_account, self.owner_generation, self.owner["id"]
        )
        self.store.select_character(
            self.other_account, self.other_generation, self.other["id"]
        )
        self.other_chest = load(
            self.store, self.other_account, self.other_generation, self.other["id"]
        )

    def _deposit(self, account, generation, character, chest, item, token):
        return transfer(
            self.store,
            account,
            generation,
            character["id"],
            12038,
            deposit_body(item["uid"], item["quantity"], compartment=chest["id"]),
            opening_token=token,
            location=dict(
                character, map_id=9, instance_id=character["haven_bag"]["owner_id"]
            ),
        )

    def test_shared_account_custody_and_foreign_account_fence(self):
        item = grant(
            self.store,
            self.owner_account,
            self.owner_generation,
            self.owner["id"],
            reference=2504,
            quantity=9,
            container=self.owner["inventory_containers"][0]["uid"],
            slot=0,
            allowed_references={2504},
        )
        owner_token = uuid.uuid4()
        deposited = self._deposit(
            self.owner_account,
            self.owner_generation,
            self.owner,
            self.owner_chest,
            item,
            owner_token,
        )
        self.assertEqual(deposited["chest"]["items"][0]["item"]["uid"], item["uid"])
        self.store.select_character(
            self.owner_account, self.owner_generation, self.sibling["id"]
        )
        shared = load(
            self.store,
            self.owner_account,
            self.owner_generation,
            self.sibling["id"],
        )
        self.assertEqual(shared["id"], self.owner_chest["id"])
        self.assertEqual(shared["items"], deposited["chest"]["items"])
        self.store.select_character(
            self.owner_account, self.owner_generation, self.owner["id"]
        )

        foreign = load(
            self.store, self.other_account, self.other_generation, self.other["id"]
        )
        self.assertNotEqual(foreign["id"], self.owner_chest["id"])
        before_other = self.store.character(self.other_account, self.other["id"])
        with self.assertRaises(ValueError):
            self._deposit(
                self.other_account,
                self.other_generation,
                self.other,
                foreign,
                item,
                owner_token,
            )
        foreign_withdraw = withdraw_body(
            self.other["id"],
            2504,
            1,
            self.other["inventory_containers"][0]["uid"],
            compartment=self.owner_chest["id"],
        )
        with self.assertRaises(ValueError):
            transfer(
                self.store,
                self.other_account,
                self.other_generation,
                self.other["id"],
                12551,
                foreign_withdraw,
                opening_token=owner_token,
                location=dict(
                    self.other,
                    map_id=9,
                    instance_id=self.other["haven_bag"]["owner_id"],
                ),
            )

        self.assertEqual(
            load(
                self.store, self.owner_account, self.owner_generation, self.owner["id"]
            )["items"],
            deposited["chest"]["items"],
        )
        self.assertEqual(
            self.store.character(self.owner_account, self.owner["id"])[
                "inventory_items"
            ],
            [],
        )
        self.assertEqual(
            self.store.character(self.other_account, self.other["id"]), before_other
        )

    def test_guest_cannot_open_host_account_chest(self):
        owner = dict(self.owner, haven_bag={"owner_id": self.owner["id"], "rooms": []})
        guest_session = HavenBagSession(self.other, owner=owner)
        guest = guest_session.move(guest_session.inside, dict(x=0, y=0, z=0))
        body = struct.pack(">qHH", 99001, 12, 0)
        host_object = dict(id=99001, type="AccountChest", map_id=9, x=0, y=0, z=0)
        with self.assertRaisesRegex(ValueError, "owner"):
            validate_open(
                guest,
                guest_session,
                body,
                [host_object],
                fight_active=False,
            )
