"""Original visual-item request grammar, custody and native consumption flags."""
import struct
import unittest
from unittest.mock import patch

from postgres_case import PostgresCase
from wakfu_server import script_item_actions as actions
from wakfu_server.inventory_items import grant


class ScriptItemWireTests(unittest.TestCase):
    def test_native_optional_position_and_output_decode(self):
        base = struct.pack(">iq", 904, 123)
        self.assertEqual(actions._request(base + b"\0"), (904, 123, None))
        self.assertEqual(
            actions._request(base + b"\1" + struct.pack(">iih", -2, 32, -1)),
            (904, 123, (-2, 32, -1)),
        )
        for suffix in (b"", b"\2", b"\1", b"\0" + b"\0" * 10):
            with self.subTest(suffix=suffix), self.assertRaises(ValueError):
                actions.action_class(base + suffix)
        self.assertIsNone(actions.action_class(struct.pack(">iq", 480, 123)))
        opcode, body = actions.script_packet(123, 904, (-2, 32, -1))
        self.assertEqual(opcode, 13270)
        self.assertEqual(struct.unpack_from(">qiBi", body), (123, 904, 0, 4))
        offset = 17
        variables = {}
        for _ in range(4):
            length = struct.unpack_from(">i", body, offset)[0]
            offset += 4
            key = body[offset : offset + length].decode()
            offset += length
            variables[key] = struct.unpack_from(">q", body, offset)[0]
            offset += 8
        self.assertEqual(offset, len(body))
        self.assertEqual(
            variables, dict(user=123, castCellX=-2, castCellY=32, castCellZ=-1)
        )
        for identity in (1, 9040000):
            with self.assertRaises(ValueError):
                actions.script_packet(123, identity, (0, 0, 0))


class ScriptItemPostgresTests(PostgresCase):
    def fixture(self, suffix=""):
        username = "script-reader" + ("_" + suffix if suffix else "")
        name = "Script Actor" + (" " + suffix if suffix else "")
        account = self.store.register(username, "local-password")["id"]
        character = self.store.create_character(account, name)
        generation = self.store.begin_session(account)
        self.store.select_character(account, generation, character["id"])
        return account, generation, character

    def give(self, account, generation, character, ref, slot, quantity=2):
        container = next(
            row for row in character["inventory_containers"] if row["kind"] == 0
        )
        return grant(
            self.store,
            account,
            generation,
            character["id"],
            reference=ref,
            quantity=quantity,
            container=container["uid"],
            slot=slot,
            allowed_references={ref},
        )

    def request(self, item, position=None):
        action = next(
            row["action_id"]
            for row in actions.descriptors()["items"]
            if row["item_ref"] == item["reference"]
        )
        return struct.pack(">iqB", action, item["uid"], int(position is not None)) + (
            b"" if position is None else struct.pack(">iih", *position)
        )

    def use(self, account, generation, character, body, **kwargs):
        # Swim topology itself is qualified by swimming tests; these fixtures
        # deliberately exercise the visual-item transaction, not map extraction.
        with patch("wakfu_server.swimming.at_position", return_value=False):
            return actions.use(
                self.store,
                account,
                generation,
                character["id"],
                body,
                in_fight=False,
                **kwargs
            )

    def test_41_qualified_descriptors_and_native_39_consumable_2_reusable_semantics(
        self,
    ):
        plans = actions.descriptors()["items"]
        self.assertEqual(len(plans), 41)
        self.assertEqual(sum(row["consumes_source"] for row in plans), 39)
        account, generation, character = self.fixture()
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM native_script_item_actions"
                ).fetchone()["n"],
                41,
            )
        reusable_count = 0
        for plan in plans:
            ref = plan["item_ref"]
            item = self.give(
                account, generation, character, ref, reusable_count, quantity=1
            )
            for _ in range(1 if plan["consumes_source"] else 2):
                result = self.use(
                    account,
                    generation,
                    character,
                    self.request(item),
                    target_present=plan["requires_mobile_target"],
                )
                self.assertEqual(
                    (result["native_class"], result["script_packet"][0]), ("bIa", 13270)
                )
                self.assertEqual(result["consumed"], int(plan["consumes_source"]))
                self.assertEqual(len(result["packets"]), int(plan["consumes_source"]))
            restored = self.reopen().character(account, character["id"])
            source = next(
                (
                    row
                    for row in restored["inventory_items"]
                    if row["uid"] == item["uid"]
                ),
                None,
            )
            self.assertEqual(source is None, plan["consumes_source"])
            if source is not None:
                self.assertEqual(source["quantity"], 1)
                reusable_count += 1
        self.assertEqual(reusable_count, 2)

    def test_rejections_never_consume_and_optional_cell_uses_scene_authority(self):
        account, generation, character = self.fixture()
        item = self.give(account, generation, character, 9724, 0)
        body = self.request(item)
        other, other_generation, other_character = self.fixture("Other")
        invalid_calls = [
            lambda: self.use(other, other_generation, other_character, body),
            lambda: self.use(account, "stale", character, body),
            lambda: self.use(
                account,
                generation,
                character,
                body,
                location=dict(character, id=other_character["id"]),
            ),
            lambda: actions.use(
                self.store, account, generation, character["id"], body, in_fight=True
            ),
            lambda: self.use(
                account,
                generation,
                character,
                self.request(item, (1234, 5678, 0)),
                geometry=lambda mid: {"map_id": mid, "cells": []},
            ),
        ]
        for call in invalid_calls:
            with self.assertRaises(ValueError):
                call()
        target = self.give(account, generation, character, 19737, 1)
        with self.assertRaises(ValueError):
            self.use(account, generation, character, self.request(target))
        with patch(
            "wakfu_server.swimming.at_position", return_value=True
        ), self.assertRaises(ValueError):
            actions.use(
                self.store, account, generation, character["id"], body, in_fight=False
            )
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT quantity FROM inventory_items WHERE uid=%s", (item["uid"],)
                ).fetchone()["quantity"],
                2,
            )
            self.assertEqual(
                db.execute(
                    "SELECT quantity FROM inventory_items WHERE uid=%s",
                    (target["uid"],),
                ).fetchone()["quantity"],
                2,
            )
        result = self.use(
            account,
            generation,
            character,
            self.request(item, (1, 2, 3)),
            geometry=lambda mid: {"map_id": mid, "cells": [(1, 2, 3)]},
        )
        self.assertEqual((result["position"], result["consumed"]), ((1, 2, 3), 1))
        result = self.use(
            account, generation, character, self.request(target), target_present=True
        )
        self.assertEqual(result["consumed"], 1)
