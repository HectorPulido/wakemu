"""Binary scene indexing and resource encoding preserve publication payloads."""

import struct
import unittest
from unittest.mock import patch

from wakfu_server import scene_wire_native, world_static
from wakfu_server.wire import proto_field


def decode(bodies):
    rows = []
    for body in bodies:
        count = struct.unpack_from(">h", body)[0]
        cursor = 2
        for _ in range(count):
            identity, size = struct.unpack_from(">qh", body, cursor)
            cursor += 10
            rows.append((identity, body[cursor : cursor + size]))
            cursor += size
        assert cursor == len(body)
    return rows


class SceneWireNativeTests(unittest.TestCase):
    def test_warm_immutable_snapshot_reuses_finished_bytes_without_catalog_or_ffi(self):
        # Use an otherwise unique entrance set to avoid depending on test order.
        chunks, entrances = ((-13, -3),), (-9223372036854775807,)
        with patch.object(
            scene_wire_native, "_register", wraps=scene_wire_native._register
        ) as register:
            first = scene_wire_native.selected_snapshots(527, chunks, entrances)
            with patch.object(
                scene_wire_native, "_call", side_effect=AssertionError("warm FFI call")
            ):
                second = scene_wire_native.selected_snapshots(527, chunks, entrances)
            self.assertIs(first, second)
            self.assertLessEqual(register.call_count, 1)

    def test_mutable_fixture_changes_payload_coordinates_and_entrance_policy(self):
        rows = [{"id": 7, "x": -19, "y": 18}]
        state = [b"original"]
        with patch.object(
            world_static, "objects", side_effect=lambda _: tuple(rows)
        ), patch.object(world_static, "dynamic_state", side_effect=lambda *_: state[0]):
            self.assertEqual(
                decode(scene_wire_native.selected_snapshots(527, [(-2, 1)], [])),
                [(7, b"original")],
            )
            state[0] = b"changed"
            self.assertEqual(
                decode(scene_wire_native.selected_snapshots(527, [(-2, 1)], [])),
                [(7, b"changed")],
            )
            self.assertEqual(
                decode(scene_wire_native.selected_snapshots(527, [(-2, 1)], [7])),
                [(7, world_static._DUNGEON_ENTRY_STATE)],
            )
            rows[0]["x"] = 1
            self.assertEqual(
                scene_wire_native.selected_snapshots(527, [(-2, 1)], []), ()
            )
            self.assertEqual(
                decode(scene_wire_native.selected_snapshots(527, [(0, 1)], [])),
                [(7, b"changed")],
            )

    def test_immutable_cache_key_includes_entrance_override_bytes(self):
        row = world_static.objects(527)[0]
        chunks = [(int(row["x"] // 18), int(row["y"] // 18))]
        before = dict(
            decode(scene_wire_native.selected_snapshots(527, chunks, [row["id"]]))
        )
        with patch.object(world_static, "_DUNGEON_ENTRY_STATE", b"replacement-state"):
            after = dict(
                decode(scene_wire_native.selected_snapshots(527, chunks, [row["id"]]))
            )
        self.assertEqual(before[row["id"]], world_static._DUNGEON_ENTRY_STATE)
        self.assertEqual(after[row["id"]], b"replacement-state")

    def test_one_native_resource_batch_preserves_negative_varints_and_filters_chunks(
        self,
    ):
        rows = [
            dict(resource_reference=4275, x=-19, y=18, z=-4, stage=2),
            dict(resource_reference=99, x=0, y=0, z=0, stage=1),
        ]
        expected = b"".join(
            proto_field(tag, value if value >= 0 else (1 << 64) + value)
            for tag, value in (
                (8, 4275),
                (16, -19),
                (24, 18),
                (32, -4),
                (40, 2),
                (48, 0),
                (56, 0),
                (64, 0),
            )
        )
        with patch.object(
            scene_wire_native, "_call", wraps=scene_wire_native._call
        ) as call:
            self.assertEqual(
                scene_wire_native.resource_packets(rows, {(-2, 1)}), [(13135, expected)]
            )
            self.assertEqual(call.call_count, 1)
            self.assertEqual(call.call_args.args[0], 15)

    def test_malformed_partition_width_is_rejected_before_flattening(self):
        for chunks in ([(1, 2, 3)], [(1,)], [(True, 2)], [(1.0, 2)]):
            with self.subTest(chunks=chunks), self.assertRaises(ValueError):
                scene_wire_native.selected_snapshots(527, chunks, [])
        with patch.object(
            scene_wire_native,
            "_call",
            side_effect=AssertionError("empty selection FFI"),
        ):
            self.assertEqual(scene_wire_native.selected_snapshots(527, [], []), ())

    def test_native_index_eviction_rebuilds_from_immutable_source(self):
        real = scene_wire_native._call
        attempts = []

        def dispatch(op, *args, **kwargs):
            attempts.append(op)
            if op == 11 and attempts.count(11) == 1:
                raise scene_wire_native.NativeSpatialError(
                    "scene_cache_miss", "evicted"
                )
            return real(op, *args, **kwargs)

        with patch.object(scene_wire_native, "_call", side_effect=dispatch):
            result = scene_wire_native.selected_snapshots(
                527, [(-12, -3)], [-9223372036854775806]
            )
        self.assertIsInstance(result, tuple)
        self.assertEqual(attempts.count(11), 2)
        self.assertIn(10, attempts)
