import struct
import ast
from pathlib import Path
from types import SimpleNamespace
import unittest

from postgres_case import PostgresCase
from wakfu_server.inventory_items import grant
from wakfu_server.haven_bag_transfer import (
    can_transfer,
    insert,
    remove,
    decode_insert,
    decode_remove,
)


class HavenBagTransferTests(PostgresCase):
    def setUp(self):
        super().setUp()
        self.account = self.store.register("gem-owner", "local-password")["id"]
        self.character = self.store.create_character(self.account, "Gem Owner")
        self.generation = self.store.begin_session(self.account)
        self.store.select_character(self.account, self.generation, self.character["id"])
        self.container = self.character["inventory_containers"][0]["uid"]

    def _gem(self, quantity=1, *, slot=0):
        return grant(
            self.store,
            self.account,
            self.generation,
            self.character["id"],
            reference=4263,
            quantity=quantity,
            container=self.container,
            slot=slot,
            allowed_references={4263},
        )

    def _insert_body(self, uid, room=1):
        return struct.pack(">qBB", uid, room, 0)

    def test_native_request_decoders_enforce_complete_bodies_and_selector(self):
        insert_body = self._insert_body(1001, 2)
        self.assertEqual(decode_insert(insert_body), {"uid": 1001, "room": 2})
        remove_body = struct.pack(">qBBB", 2001, 3, 2, 0)
        self.assertEqual(
            decode_remove(remove_body),
            {"container": 2001, "position": 3, "room": 2, "primary": False},
        )
        for body in (insert_body[:-1], insert_body[:-1] + b"\x01", b"\x00" * 10):
            with self.assertRaises(ValueError):
                decode_insert(body)
        for body in (
            remove_body[:-1],
            remove_body + b"\x00",
            remove_body[:-1] + b"\x02",
        ):
            with self.assertRaises(ValueError):
                decode_remove(body)

    def test_stack_insert_splits_one_unit_with_new_uid_and_retry_is_idempotent(self):
        item = self._gem(quantity=3)
        location = {"map_id": 9, "instance_id": self.character["id"]}
        result = insert(
            self.store,
            self.account,
            self.generation,
            self.character["id"],
            self._insert_body(item["uid"]),
            location=location,
        )
        self.assertFalse(result["replayed"])
        self.assertNotEqual(result["uid"], item["uid"])
        self.assertEqual([op for op, _ in result["packets"]], [12470, 12471, 12234])
        self.assertEqual(result["packets"][0][1], struct.pack(">qh", item["uid"], -1))
        split_container, split_slot, proto_size = struct.unpack_from(
            ">qhI", result["packets"][1][1]
        )
        proto = result["packets"][1][1][14 : 14 + proto_size]
        from wakfu_server.wire import proto_fields

        split_fields = dict(proto_fields(proto))
        self.assertEqual(split_container, self.container)
        self.assertEqual(split_slot, 1)
        self.assertEqual(
            (split_fields[8], split_fields[16], split_fields[24]),
            (result["uid"], 4263, 1),
        )
        self.assertEqual(result["packets"][1][1][-1:], b"\x00")
        self.assertEqual(result["packets"][2][1], struct.pack(">qB", result["uid"], 1))
        persisted = self.store.character(self.account, self.character["id"])
        self.assertEqual(persisted["inventory_items"][0]["quantity"], 2)
        room = next(x for x in persisted["haven_bag"]["rooms"] if x["index"] == 1)
        self.assertEqual(
            (room["primary_ref"], room["primary_uid"]), (4263, result["uid"])
        )
        with self.store.connection() as db:
            self.assertIsNone(
                db.execute(
                    "SELECT 1 FROM inventory_items WHERE uid=%s", (result["uid"],)
                ).fetchone()
            )
            self.assertIsNotNone(
                db.execute(
                    "SELECT 1 FROM haven_bag_gems WHERE uid=%s", (result["uid"],)
                ).fetchone()
            )

        replay = insert(
            self.store,
            self.account,
            self.generation,
            self.character["id"],
            self._insert_body(item["uid"]),
            location=location,
        )
        self.assertTrue(replay["replayed"])
        self.assertEqual(replay["uid"], result["uid"])
        self.assertEqual(
            self.store.character(self.account, self.character["id"])["inventory_items"][
                0
            ]["quantity"],
            2,
        )

    def test_insert_then_remove_returns_original_uid_and_survives_reopen(self):
        item = self._gem()
        location = {"map_id": 9, "instance_id": self.character["id"]}
        installed = insert(
            self.store,
            self.account,
            self.generation,
            self.character["id"],
            self._insert_body(item["uid"]),
            location=location,
        )
        removed = remove(
            self.store,
            self.account,
            self.generation,
            self.character["id"],
            struct.pack(">qBBB", self.container, 1, 1, 1),
            location=location,
        )
        self.assertEqual(removed["uid"], item["uid"])
        self.assertEqual([op for op, _ in removed["packets"]], [12451, 12471])
        self.assertEqual(
            removed["packets"][0],
            (12451, struct.pack(">qBBB", self.container, 1, 1, 1)),
        )
        from wakfu_server.inventory_items import insertion

        self.assertEqual(
            removed["packets"][1], insertion(removed["character"]["inventory_items"][0])
        )
        reopened = self.reopen().character(self.account, self.character["id"])
        self.assertEqual(
            [
                (x["uid"], x["reference"], x["quantity"], x["slot"])
                for x in reopened["inventory_items"]
            ],
            [(item["uid"], 4263, 1, 1)],
        )
        room = next(x for x in reopened["haven_bag"]["rooms"] if x["index"] == 1)
        self.assertEqual(
            (room["primary_ref"], room["primary_uid"], room["enabled"]), (-1, 0, False)
        )
        self.assertEqual(installed["uid"], item["uid"])

    def test_secondary_selector_is_preserved_and_item_state_is_restored(self):
        from wakfu_server.inventory_shards import validate

        item = grant(
            self.store,
            self.account,
            self.generation,
            self.character["id"],
            reference=4262,
            quantity=1,
            container=self.container,
            slot=0,
            allowed_references={4262},
        )
        shard_state = b"\x0a\x02\x50\x00"
        validate(shard_state)
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO inventory_item_elements(uid,damage_elements,resistance_elements) VALUES(%s,10,20)",
                (item["uid"],),
            )
            db.execute(
                "INSERT INTO inventory_item_shards(uid,shard_state) VALUES(%s,%s)",
                (item["uid"], shard_state),
            )
        location = {"map_id": 9, "instance_id": self.character["id"]}
        inserted = insert(
            self.store,
            self.account,
            self.generation,
            self.character["id"],
            self._insert_body(item["uid"], room=0),
            location=location,
        )
        config = self.store.character(self.account, self.character["id"])["haven_bag"]
        entrance = next(row for row in config["rooms"] if row["index"] == 0)
        self.assertEqual(
            (entrance["primary_ref"], entrance["primary_uid"]),
            (4262, self.character["id"] * 256 + 1),
        )
        self.assertEqual(
            (entrance["secondary_ref"], entrance["secondary_uid"]), (4262, item["uid"])
        )
        removed = remove(
            self.store,
            self.account,
            self.generation,
            self.character["id"],
            struct.pack(">qBBB", self.container, 0, 0, 0),
            location=location,
        )
        self.assertEqual(removed["uid"], item["uid"])
        self.assertEqual([op for op, _ in removed["packets"]], [12451, 12471])
        from wakfu_server.inventory_items import insertion

        restored_item = next(
            row
            for row in removed["character"]["inventory_items"]
            if row["uid"] == item["uid"]
        )
        self.assertEqual(restored_item["damage_elements"], 10)
        self.assertEqual(restored_item["resistance_elements"], 20)
        self.assertEqual(bytes(restored_item["shard_state"]), shard_state)
        self.assertEqual(removed["packets"][1], insertion(restored_item))
        with self.store.connection() as db:
            restored = db.execute(
                "SELECT damage_elements,resistance_elements FROM inventory_item_elements WHERE uid=%s",
                (item["uid"],),
            ).fetchone()
            shard = db.execute(
                "SELECT shard_state FROM inventory_item_shards WHERE uid=%s",
                (item["uid"],),
            ).fetchone()
        self.assertEqual(
            (restored["damage_elements"], restored["resistance_elements"]), (10, 20)
        )
        self.assertEqual(bytes(shard["shard_state"]), shard_state)
        self.assertEqual(inserted["uid"], item["uid"])

    def test_stack_insert_fails_closed_without_free_temporary_slot(self):
        item = self._gem(quantity=2)
        with self.store.connection() as db:
            capacity = db.execute(
                "SELECT capacity FROM inventory_containers WHERE uid=%s",
                (self.container,),
            ).fetchone()["capacity"]
        # Fill every other position in the permanent bag; the requested stack
        # cannot be split into a client-visible one-unit item safely.
        from wakfu_server.inventory_items import grant as grant_item

        for slot in range(1, capacity):
            grant_item(
                self.store,
                self.account,
                self.generation,
                self.character["id"],
                reference=100,
                quantity=1,
                container=self.container,
                slot=slot,
                allowed_references={100},
            )
        with self.assertRaisesRegex(ValueError, "free inventory slot"):
            insert(
                self.store,
                self.account,
                self.generation,
                self.character["id"],
                self._insert_body(item["uid"]),
                location={"map_id": 9, "instance_id": self.character["id"]},
            )
        persisted = self.store.character(self.account, self.character["id"])
        source = next(
            row for row in persisted["inventory_items"] if row["uid"] == item["uid"]
        )
        self.assertEqual(source["quantity"], 2)
        self.assertFalse(
            any(
                row["index"] == 1 and row["primary_ref"] != -1
                for row in persisted["haven_bag"]["rooms"]
            )
        )

    def test_invalid_owner_location_destination_or_gem_rolls_back(self):
        item = self._gem()
        with self.assertRaises(ValueError):
            insert(
                self.store,
                self.account,
                self.generation,
                self.character["id"],
                self._insert_body(item["uid"]),
                location={"map_id": 9, "instance_id": self.character["id"] + 1},
            )
        self.assertEqual(
            self.store.character(self.account, self.character["id"])["inventory_items"][
                0
            ]["quantity"],
            1,
        )
        foreign = self.store.register("other-gem-owner", "local-password")["id"]
        other = self.store.create_character(foreign, "Other Gem Owner")
        with self.assertRaises(ValueError):
            insert(
                self.store,
                self.account,
                self.generation,
                other["id"],
                self._insert_body(item["uid"]),
                location={"map_id": 9, "instance_id": other["id"]},
            )
        with self.assertRaises(ValueError):
            remove(
                self.store,
                self.account,
                self.generation,
                self.character["id"],
                struct.pack(">qBBB", self.container, 1, 1, 1),
                location={"map_id": 9, "instance_id": self.character["id"]},
            )
        self.assertEqual(
            self.store.character(self.account, self.character["id"])["inventory_items"][
                0
            ]["uid"],
            item["uid"],
        )

    def test_transaction_rollback_preserves_item_and_layout(self):
        item = self._gem(quantity=2)
        with self.assertRaises(ValueError):
            insert(
                self.store,
                self.account,
                self.generation,
                self.character["id"],
                self._insert_body(item["uid"], room=0),
                location={"map_id": 9, "instance_id": self.character["id"]},
            )
        persisted = self.store.character(self.account, self.character["id"])
        self.assertEqual(persisted["inventory_items"][0]["quantity"], 2)
        self.assertFalse(
            any(
                r["index"] == 0 and r["secondary_ref"] == 4263
                for r in persisted["haven_bag"]["rooms"]
            )
        )

    def test_moving_secondary_gem_updates_relational_owner_record(self):
        from wakfu_server.haven_bag_store import rearrange_rooms, save
        from wakfu_server.inventory_items import grant

        item = grant(
            self.store,
            self.account,
            self.generation,
            self.character["id"],
            reference=4262,
            quantity=1,
            container=self.container,
            slot=0,
            allowed_references={4262},
        )
        location = {"map_id": 9, "instance_id": self.character["id"]}
        insert(
            self.store,
            self.account,
            self.generation,
            self.character["id"],
            self._insert_body(item["uid"], room=0),
            location=location,
        )

        current = self.store.character(self.account, self.character["id"])
        moved_rooms = rearrange_rooms(current["haven_bag"], bytes((0, 1, 0, 1)))
        save(
            self.store,
            self.account,
            self.generation,
            self.character["id"],
            rooms=moved_rooms,
        )

        reopened = self.reopen()
        reopened_character = reopened.character(self.account, self.character["id"])
        room = next(
            row for row in reopened_character["haven_bag"]["rooms"] if row["index"] == 1
        )
        self.assertEqual(
            (room["primary_ref"], room["primary_uid"]), (4262, item["uid"])
        )
        removed = remove(
            reopened,
            self.account,
            self.generation,
            self.character["id"],
            struct.pack(">qBBB", self.container, 0, 1, 1),
            location=location,
        )
        self.assertEqual(removed["uid"], item["uid"])
        self.assertEqual(
            reopened.character(self.account, self.character["id"])["inventory_items"][
                0
            ]["uid"],
            item["uid"],
        )

    def test_last_room_gem_cannot_be_removed_while_visitors_or_furniture_remain(self):
        from psycopg.types.json import Jsonb

        item = self._gem()
        location = {"map_id": 9, "instance_id": self.character["id"]}
        insert(
            self.store,
            self.account,
            self.generation,
            self.character["id"],
            self._insert_body(item["uid"]),
            location=location,
        )
        remove_body = struct.pack(">qBBB", self.container, 1, 1, 1)
        with self.assertRaisesRegex(ValueError, "visitors"):
            remove(
                self.store,
                self.account,
                self.generation,
                self.character["id"],
                remove_body,
                location={**location, "other_occupants": True},
            )
        with self.store.connection() as db:
            db.execute(
                "UPDATE haven_bags SET furniture=%s WHERE character_id=%s",
                (
                    Jsonb(
                        [
                            {
                                "room": 1,
                                "deployed": True,
                                "template_id": 100,
                                "item_uid": 1001,
                            }
                        ]
                    ),
                    self.character["id"],
                ),
            )
        with self.assertRaisesRegex(ValueError, "furniture"):
            remove(
                self.store,
                self.account,
                self.generation,
                self.character["id"],
                remove_body,
                location=location,
            )
        persisted = self.store.character(self.account, self.character["id"])
        room = next(row for row in persisted["haven_bag"]["rooms"] if row["index"] == 1)
        self.assertEqual(
            (room["primary_ref"], room["primary_uid"]), (4263, item["uid"])
        )
        self.assertFalse(
            any(row["uid"] == item["uid"] for row in persisted["inventory_items"])
        )


class HavenBagTransferDispatchTests(unittest.TestCase):
    def test_dispatch_guard_requires_own_bag_and_no_fight(self):
        class BagSession:
            is_owner = True

            def owns(self, character):
                return (
                    character["id"] == 8
                    and character["map_id"] == 9
                    and character["instance_id"] == 8
                )

        owner = {"id": 8, "map_id": 9, "instance_id": 8}
        visitor = {"id": 9, "map_id": 9, "instance_id": 8}
        self.assertTrue(can_transfer(BagSession(), owner, fight_active=False))
        self.assertFalse(can_transfer(BagSession(), owner, fight_active=True))
        self.assertFalse(can_transfer(BagSession(), visitor, fight_active=False))
        self.assertFalse(can_transfer(None, owner, fight_active=False))
        self.assertFalse(can_transfer(BagSession(), owner, fight_active=1))

    def test_local_dispatcher_routes_only_the_two_verified_transfer_opcodes(self):
        source = Path(__file__).resolve().parents[1] / "local_game_server.py"
        module = ast.parse(source.read_text())
        session = next(
            node
            for node in module.body
            if isinstance(node, ast.FunctionDef) and node.name == "session"
        )
        branches = [
            node
            for node in ast.walk(session)
            if isinstance(node, ast.If)
            and any(
                isinstance(test, ast.Compare)
                and isinstance(test.left, ast.Name)
                and test.left.id == "opcode"
                and isinstance(test.ops[0], ast.In)
                and isinstance(test.comparators[0], (ast.Tuple, ast.List, ast.Set))
                and {
                    value.value
                    for value in test.comparators[0].elts
                    if isinstance(value, ast.Constant)
                }
                == {12177, 13090}
                for test in (
                    node.test.values
                    if isinstance(node.test, ast.BoolOp)
                    else (node.test,)
                )
            )
        ]
        self.assertEqual(len(branches), 1)
        branch = branches[0]
        names = {
            node.func.id
            for statement in branch.body
            for node in ast.walk(statement)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        }
        self.assertTrue({"can_transfer", "insert", "remove", "send", "record"} <= names)
        self.assertFalse(
            any(
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id in {"grant", "save_haven_bag"}
                for statement in branch.body
                for node in ast.walk(statement)
            )
        )
