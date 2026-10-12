"""Exercise protector records at the actual world-bootstrap boundaries."""
import ast
from contextlib import contextmanager
import struct
import unittest
from unittest.mock import Mock, patch

from types import SimpleNamespace
from pathlib import Path
from wakfu_server.maps import npc_protectors, npc_world
from test_owned_native_bootstrap import SERVER, _extract_bootstrap
from test_npc_protectors import otomai


def _native_bootstrap():
    source = (
        Path(__file__).resolve().parents[1] / "wakfu_server/maps/native_transports.py"
    )
    tree = ast.parse(source.read_text(encoding="utf8"))
    node = next(
        item
        for item in tree.body
        if isinstance(item, ast.FunctionDef) and item.name == "bootstrap"
    )
    namespace = {
        "struct": struct,
        "__name__": "wakfu_server.maps.native_transports",
        "__package__": "wakfu_server.maps",
    }
    exec(
        compile(
            ast.fix_missing_locations(ast.Module(body=[node], type_ignores=[])),
            str(source),
            "exec",
        ),
        namespace,
    )
    return SimpleNamespace(bootstrap=namespace["bootstrap"])


native_transports = _native_bootstrap()


def blocks(payload):
    result = []
    offset = 0
    while offset < len(payload):
        length = struct.unpack_from(">H", payload, offset)[0]
        offset += 2
        result.append(payload[offset : offset + length])
        offset += length
    if offset != len(payload):
        raise AssertionError("Truncated native bootstrap block")
    return result


class ProtectorBootstrapIntegrationTests(unittest.TestCase):
    def setUp(self):
        # These tests pin native block framing and transport boundaries. The
        # tax policy/territory enrichment contract has its own focused suite.
        self.message_records = patch(
            "wakfu_server.maps.protector_ecosystem.message_records",
            side_effect=lambda _map_id, records=(), *, instance_id=0: (
                records if records is None else tuple(records)
            ),
        )
        self.message_records.start()
        self.addCleanup(self.message_records.stop)
        self.character = dict(
            id=701, account_id=19, map_id=1385, instance_id=0, x=20, y=17, z=1
        )

    def test_real_native_message_preserves_all_other_blocks_and_record_framing(self):
        original = native_transports.bootstrap(self.character)
        record = npc_protectors.record(otomai())
        packets = native_transports.bootstrap(
            self.character, protector_records=(record,)
        )
        self.assertEqual([13256, 13974, 12318], [opcode for opcode, _ in packets])
        self.assertEqual(original[0], packets[0])
        self.assertEqual(original[2], packets[2])
        before, after = blocks(original[1][1]), blocks(packets[1][1])
        self.assertEqual(4, len(after))
        self.assertEqual(b"\0\0", before[1])
        self.assertEqual(struct.pack(">HH", 1, 41) + record, after[1])
        for index in (0, 2, 3):
            self.assertEqual(before[index], after[index])
        self.assertEqual(
            original, native_transports.bootstrap(self.character, protector_records=[])
        )

    def test_invalid_native_record_containers_counts_and_lengths_fail_closed(self):
        for records in (
            None,
            b"record",
            (b"",),
            (bytearray(b"a"),),
            (b"a" * 32768,),
            [b"a"] * 32768,
        ):
            with self.subTest(kind=type(records).__name__), self.assertRaises(
                ValueError
            ):
                native_transports.bootstrap(self.character, protector_records=records)

    def test_total_protector_block_checks_outer_unsigned_short_limit(self):
        packets = native_transports.bootstrap(
            self.character, protector_records=(b"a" * 32767, b"b" * 32762)
        )
        self.assertEqual(65535, len(blocks(packets[1][1])[1]))
        with self.assertRaisesRegex(ValueError, "frame capacity"):
            native_transports.bootstrap(
                self.character, protector_records=(b"a" * 32767, b"b" * 32763)
            )

    def test_public_protector_map_uses_owned_connection_and_publishes_exact_records(
        self,
    ):
        db = object()
        record = npc_protectors.record(otomai())
        store = Mock()

        @contextmanager
        def connection():
            yield db

        store.connection.side_effect = connection
        bootstrap = _extract_bootstrap(SERVER)
        with patch.object(
            npc_protectors, "bootstrap_records", return_value=(record,)
        ) as loader, patch.dict(
            bootstrap.__globals__,
            dict(
                STORE=store,
                is_dungeon_run=lambda _: False,
                native_transports=native_transports,
            ),
        ):
            result = bootstrap(self.character)
        loader.assert_called_once_with(db, self.character)
        store.connection.assert_called_once_with()
        self.assertEqual(struct.pack(">HH", 1, 41) + record, blocks(result[1][1])[1])

    def test_other_public_maps_and_private_protector_map_never_query_protectors(self):
        bootstrap = _extract_bootstrap(SERVER)
        store = Mock()
        with patch.object(npc_protectors, "bootstrap_records") as loader, patch.dict(
            bootstrap.__globals__,
            dict(
                STORE=store,
                is_dungeon_run=lambda _: False,
                native_transports=native_transports,
            ),
        ):
            for map_id, instance_id in ((1385, 77), (1388, 0), (1134, 0)):
                character = dict(self.character, map_id=map_id, instance_id=instance_id)
                self.assertEqual(
                    native_transports.bootstrap(character), bootstrap(character)
                )
        loader.assert_not_called()
        store.connection.assert_not_called()

    def test_actual_open_request_generator_uses_protector_speaker_identity(self):
        tree = ast.parse(SERVER.read_text(encoding="utf8"))
        generators = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.GeneratorExp)
            and any(
                isinstance(call, ast.Call)
                and isinstance(call.func, ast.Attribute)
                and call.func.attr == "matches_open_request"
                for call in ast.walk(node)
            )
        ]
        self.assertEqual(1, len(generators))
        expression = ast.Expression(body=generators[0])
        code = compile(ast.fix_missing_locations(expression), str(SERVER), "eval")
        row = otomai()
        for kind, identity, root, expected in (
            (1, 424, 5772, row),
            (2, row["actor_id"], 5772, None),
            (1, 425, 5772, None),
            (1, 424, 5773, None),
        ):
            with self.subTest(kind=kind, identity=identity, root=root):
                namespace = dict(
                    npc_world=npc_world,
                    dialogue_rows=lambda: [row],
                    request=dict(speaker_type=kind, speaker_id=identity, node_id=root),
                )
                self.assertEqual(expected, next(eval(code, namespace), None))


if __name__ == "__main__":
    unittest.main()
