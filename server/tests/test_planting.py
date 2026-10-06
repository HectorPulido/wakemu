import struct
import unittest
from postgres_case import PostgresCase
from wakfu_server.inventory_items import grant
from wakfu_server.planting import prepare, complete, publish_groups, SEEDS, RESOURCES
from wakfu_server.monsters import owned_instance
from wakfu_server.combat_groups import Groups


class PlantingTests(PostgresCase):
    def setUp(self):
        super().setUp()
        self.account = self.store.register("planting", "password")["id"]
        self.char = self.store.create_character(self.account, "Planting Player")
        self.generation = self.store.begin_session(self.account)
        self.store.select_character(self.account, self.generation, self.char["id"])

    def seed(self, ref):
        item = grant(
            self.store,
            self.account,
            self.generation,
            self.char["id"],
            reference=ref,
            quantity=3,
            container=self.char["inventory_containers"][0]["uid"],
            slot=0,
            allowed_references=SEEDS,
        )
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO character_professions VALUES(%s,%s,%s)",
                (self.char["id"], SEEDS[ref]["profession_id"], 200),
            )
        body = struct.pack(">iqii", SEEDS[ref]["action_id"], item["uid"], 10, 11)
        prepared = prepare(
            self.store,
            self.account,
            self.generation,
            self.char,
            body,
            authorize_cell=lambda *args: 0,
        )
        return item, body, prepared

    def test_herbalist_resource_and_owned_consumption_once(self):
        item, body, p = self.seed(4275)
        kwargs = dict(
            operation_id="herb-1", stage=1, creation_time=123, result_prefix=(0, 1)
        )
        result = complete(self.store, self.account, self.generation, p, **kwargs)
        self.assertEqual(
            [packet[0] for packet in result["packets"]], [13135, 12954, 12470]
        )
        self.assertEqual(
            result["packets"][2], (12470, struct.pack(">qh", item["uid"], -1))
        )
        self.assertEqual(result["resource"]["resource_reference"], 60)
        duplicate = complete(self.store, self.account, self.generation, p, **kwargs)
        self.assertTrue(duplicate["duplicate"])
        self.assertEqual(duplicate["packets"], [])
        self.assertEqual(
            self.store.character(self.account, self.char["id"])["inventory_items"][0][
                "quantity"
            ],
            2,
        )

    def test_monster_native_family_and_outbox_retry(self):
        item, body, p = self.seed(30927)
        member = owned_instance(
            5525, 1, -2000, map_id=self.char["map_id"], x=10, y=11, z=0
        )
        complete(
            self.store,
            self.account,
            self.generation,
            p,
            operation_id="monster-1",
            stage=1,
            creation_time=123,
            result_prefix=(0, 1),
            monster_members=[member],
            group_id=2000,
        )

        class Failed:
            def register(self, *args):
                raise ConnectionError("Group registry unavailable")

        with self.assertRaises(ConnectionError):
            publish_groups(self.store, Failed())
        self.assertEqual(
            self.store.character(self.account, self.char["id"])["inventory_items"][0][
                "quantity"
            ],
            2,
        )
        groups = Groups()
        self.assertEqual(publish_groups(self.store, groups)[0][0], 12608)
        self.assertEqual(publish_groups(self.store, groups), [])
        self.assertEqual(len(groups.available(self.char["map_id"], 0)), 1)

    def test_bad_stage_rolls_back_and_unlearned_rejected(self):
        item, body, p = self.seed(4275)
        with self.assertRaises(ValueError):
            complete(
                self.store,
                self.account,
                self.generation,
                p,
                operation_id="bad",
                stage=127,
                creation_time=1,
                result_prefix=(0, 1),
            )
        self.assertEqual(
            self.store.character(self.account, self.char["id"])["inventory_items"][0][
                "quantity"
            ],
            3,
        )
        with self.store.connection() as db:
            db.execute("DELETE FROM character_professions")
        with self.assertRaises(ValueError):
            prepare(
                self.store,
                self.account,
                self.generation,
                self.char,
                body,
                authorize_cell=lambda *args: 0,
            )
