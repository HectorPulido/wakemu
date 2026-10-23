"""Socket preservation does not require unrelated elemental choices."""
import struct

from postgres_case import PostgresCase
import test_conversion_shard_policy as shard_tests
from wakfu_server import conversion_item_actions as actions
from wakfu_server.wire import proto_field


class ConversionSocketOnlyPostgresTests(PostgresCase):
    fixture = shard_tests.ConversionShardPostgresTests.fixture
    give = shard_tests.ConversionShardPostgresTests.give
    body = shard_tests.ConversionShardPostgresTests.body

    def test_real_13787_socket_only_main_preserves_exact_state_and_reload(self):
        from wakfu_server.shard_identification import identify, _catalog

        account, generation, character = self.fixture()
        physical, selected, socket_only = [], [], []
        for plan in actions.descriptors()["items"]:
            if plan["main_reference"] <= 0:
                continue
            target = actions.main_product_contract(plan)
            physical.append(plan["item_ref"])
            try:
                actions.identified_contract(plan)
                selected.append(plan["item_ref"])
            except ValueError:
                if plan["item_ref"] in _catalog() and target in _catalog():
                    socket_only.append(plan["item_ref"])
        self.assertEqual((len(physical), len(selected)), (116, 104))
        self.assertIn(24039, socket_only)
        source = self.give(account, generation, character, 24039)
        resident = self.give(account, generation, character, 20667, slot=1)
        identified = identify(
            self.store,
            account,
            generation,
            character["id"],
            struct.pack(">q", source["uid"]),
            randbelow=lambda total: 0,
        )
        self.assertTrue(identified["applied"])
        state = identified["shard_state"]
        result = actions.use(
            self.store,
            account,
            generation,
            character["id"],
            self.body(source),
            in_fight=False,
        )
        main = next(
            row
            for row in result["character"]["inventory_items"]
            if row["reference"] == 20667 and row["uid"] != resident["uid"]
        )
        self.assertEqual(main["quantity"], 1)
        self.assertNotEqual(main["uid"], source["uid"])
        self.assertEqual(main["shard_state"], state)
        for row in result["character"]["inventory_items"]:
            if row["uid"] != main["uid"]:
                self.assertNotIn("shard_state", row)
        loaded = self.reopen().character(account, character["id"])
        self.assertEqual(
            next(row for row in loaded["inventory_items"] if row["uid"] == main["uid"])[
                "shard_state"
            ],
            state,
        )
        with self.assertRaises(ValueError):
            actions.use(
                self.store,
                account,
                generation,
                character["id"],
                self.body(source),
                in_fight=False,
            )

    def test_socket_only_invalid_state_and_unqualified_masks_roll_back(self):
        from wakfu_server.shard_identification import identify

        account, generation, character = self.fixture()
        source = self.give(account, generation, character, 24039)
        identified = identify(
            self.store,
            account,
            generation,
            character["id"],
            struct.pack(">q", source["uid"]),
            randbelow=lambda total: 0,
        )
        valid = identified["shard_state"]
        for invalid_socket, invalid_selection in ((True, False), (False, True)):
            state = valid + proto_field(800, 1) if invalid_socket else valid
            with self.store.connection() as db:
                db.execute(
                    "UPDATE inventory_item_shards SET shard_state=%s WHERE uid=%s",
                    (state, source["uid"]),
                )
                if invalid_selection:
                    db.execute(
                        "INSERT INTO inventory_item_elements(uid,damage_elements,resistance_elements) VALUES(%s,2,0) ON CONFLICT(uid) DO UPDATE SET damage_elements=2",
                        (source["uid"],),
                    )
                before = list(
                    db.execute(
                        "SELECT * FROM inventory_items WHERE character_id=%s ORDER BY uid",
                        (character["id"],),
                    )
                )
            with self.assertRaises(ValueError):
                actions.use(
                    self.store,
                    account,
                    generation,
                    character["id"],
                    self.body(source),
                    in_fight=False,
                )
            with self.store.connection() as db:
                self.assertEqual(
                    before,
                    list(
                        db.execute(
                            "SELECT * FROM inventory_items WHERE character_id=%s ORDER BY uid",
                            (character["id"],),
                        )
                    ),
                )
                self.assertEqual(
                    bytes(
                        db.execute(
                            "SELECT shard_state FROM inventory_item_shards WHERE uid=%s",
                            (source["uid"],),
                        ).fetchone()["shard_state"]
                    ),
                    state,
                )
