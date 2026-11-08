"""Native lP replacement followed by bounded cwO append events preserves all loot."""
import ast
import base64
from contextlib import contextmanager
import os
from pathlib import Path
import struct
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from wakfu_server import combat_drop_delivery as delivery
from wakfu_server.wire import proto_field


class Rows:
    def __init__(self, rows):
        self.rows = rows
        self.reads = 0

    def execute(self, sql, args=None):
        if sql.startswith("SELECT uid,character_id"):
            self.reads += 1
            return SimpleNamespace(fetchall=lambda: self.rows)
        if sql.startswith("SELECT actor_id"):
            return []
        raise AssertionError(sql)


class TemporaryInventoryOverflowTests(unittest.TestCase):
    def test_native_snapshot_chunks_and_replay_order_preserve_every_item(self):
        owner = 196
        rows = [
            dict(
                uid=800000 + i,
                character_id=owner,
                reference=12325,
                quantity=1 + i % 100,
                damage_elements=None,
                resistance_elements=None,
                bound=False,
            )
            for i in range(3000)
        ]
        db = Rows(rows)
        section, packets = delivery.temporary_bootstrap(db, owner)
        self.assertEqual(db.reads, 1)
        self.assertEqual(section, b"\0\0")
        self.assertGreater(len(packets), 1)
        # Native cwO: long owner then events until remaining()==0; only CLEAR
        # resets the model. Compare each full vj form, including all options.
        expected = [delivery._temporary_item_form(row) for row in rows]
        seen = []
        clears = 0
        for index, (opcode, body) in enumerate(packets):
            self.assertEqual(opcode, 12691)
            self.assertLessEqual(6 + len(body), 32767)
            self.assertEqual(struct.unpack(">q", body[:8])[0], owner)
            offset = 8
            if index == 0:
                self.assertEqual(body[offset], 3)
                clears += 1
                offset += 1
            while offset < len(body):
                self.assertEqual(body[offset], 0)
                form = expected[len(seen)]
                self.assertEqual(body[offset + 1 : offset + 1 + len(form)], form)
                seen.append(struct.unpack(">qih", form[:14]))
                offset += 1 + len(form)
            self.assertEqual(offset, len(body))
        self.assertEqual(clears, 1)
        self.assertEqual(
            seen, [(r["uid"], r["reference"], r["quantity"]) for r in rows]
        )
        self.assertEqual(delivery.temporary_updates(Rows(rows), owner), packets)
        self.assertEqual(
            delivery.temporary_updates(Rows([]), owner),
            [(12691, struct.pack(">qB", owner, 3))],
        )
        small = rows[:1]
        payload = proto_field(10, delivery._item_proto(small[0]))
        self.assertEqual(
            delivery.temporary_bootstrap(Rows(small), owner),
            (struct.pack(">h", len(payload)) + payload, []),
        )
        self.assertEqual(
            delivery.temporary_update(Rows(small), owner),
            delivery.temporary_updates(Rows(small), owner)[0],
        )
        # Exact lP short boundary: tag plus varint length occupies four bytes.
        with patch.object(delivery, "_item_proto", return_value=b"x" * 32763):
            self.assertEqual(
                len(delivery.temporary_bootstrap(Rows(small), owner)[0]), 32769
            )
        with patch.object(delivery, "_item_proto", return_value=b"x" * 32764):
            self.assertEqual(
                delivery.temporary_bootstrap(Rows(small), owner)[0], b"\0\0"
            )
        self.assertEqual(delivery.temporary_bootstrap(Rows([]), owner), (b"\0\0", []))

        default = Path(__file__).resolve().parents[1] / "local_game_server.py"
        source = Path(os.environ.get("TEMPORARY_REPLAY_SOURCE", default))
        tree = ast.parse(source.read_text())
        replay = next(
            n
            for n in tree.body
            if isinstance(n, ast.FunctionDef) and n.name == "replay"
        )
        emitted = []

        @contextmanager
        def connection():
            yield Rows(rows)

        store = SimpleNamespace(
            connection=connection,
            lock_character=lambda *a: None,
            account_kamas=lambda *a: 0,
        )

        def adapt(opcode, original, account, character, **kwargs):
            self.assertEqual(character["temporary_inventory_section"], b"\0\0")
            return original

        frames = [
            dict(direction="in", opcode=op, body_base64="")
            for op in (12666, 13713, 15548, 999)
        ]
        namespace = dict(
            STORE=store,
            FRAMES=frames,
            base64=base64,
            struct=struct,
            wire=SimpleNamespace(adapt=adapt),
            social=SimpleNamespace(adapt=lambda *a, **k: None),
            send=lambda *args: emitted.append(args[2:]),
        )
        exec(
            compile(
                ast.fix_missing_locations(ast.Module(body=[replay], type_ignores=[])),
                str(source),
                "exec",
            ),
            namespace,
        )
        namespace["replay"]("socket", 0, len(frames), 77, dict(id=owner, map_id=1134))
        self.assertEqual(emitted[:4], [(f["opcode"], b"") for f in frames])
        self.assertEqual(emitted[4:], packets)
        emitted.clear()
        namespace["replay"]("socket", 3, 4, 77, dict(id=owner, map_id=1134))
        self.assertEqual(emitted, [(999, b"")])
