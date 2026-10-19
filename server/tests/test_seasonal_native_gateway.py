"""Native seasonal gateway projection keeps ordinary transport authority."""
import struct
import unittest
from unittest.mock import patch

from wakfu_server import generic_transports, dungeon_instances, world_static
from wakfu_server.maps import seasonal_native_gateway as gateway
from wakfu_server.maps.interactive_publication import InteractivePublication


def frame(opcode, body=b""):
    return struct.pack(">IH", len(body) + 6, opcode) + body


def packets(data):
    result = []
    while data:
        size, opcode = struct.unpack_from(">IH", data)
        result.append((opcode, data[6:size]))
        data = data[size:]
    return result


class SeasonalNativeGatewayTests(unittest.TestCase):
    def setUp(self):
        self.routes = {}
        for map_id, source_id in ((472, 17452), (527, 20179)):
            source = generic_transports.source(map_id, source_id)
            destination = source["destinations"][0]
            route = dungeon_instances.EntryRoute(
                key=f"reviewed-{source_id}",
                template_id=1000000 + destination["map_id"],
                definition_id=1000000 + destination["map_id"],
                entry_map_id=map_id,
                entry_object_id=source_id,
                destination_id=destination["destination_id"],
                start_map_id=destination["map_id"],
                criterion=destination["criterion"],
                native_template_id=destination["cyZ"],
            )
            self.routes[route.key] = route
        self.registry = patch.object(dungeon_instances, "_ROUTES", self.routes)
        self.registry.start()
        self.addCleanup(self.registry.stop)

    def row(self, map_id, source_id):
        return next(
            row for row in world_static.objects(map_id) if row["id"] == source_id
        )

    def test_actual_native_doors_keep_geometry_and_bind_generic_activation(self):
        for map_id, source_id in ((472, 17452), (527, 20179)):
            with self.subTest(source=source_id):
                row = self.row(map_id, source_id)
                binding = gateway.binding(map_id, source_id)
                original = gateway._parts(bytes.fromhex(row["payload_hex"]))
                actual = gateway._parts(gateway.appearance(row, binding))
                self.assertEqual(set(actual), {0, 1, 2})
                self.assertEqual(actual[0], original[0])
                marker = binding["source"]["native_parameters"].encode()
                marker = struct.pack(">H", len(marker)) + marker
                prefix, suffix = original[1].split(marker)
                self.assertTrue(actual[1].startswith(prefix))
                self.assertTrue(actual[1].endswith(suffix))
                self.assertIn(b"{1;desc.mru.entrer}", actual[1])
                self.assertEqual(
                    actual[2], gateway._parts(world_static._DUNGEON_ENTRY_STATE)[2]
                )
                opcode, body = gateway.attachment(
                    row, dict(map_id=map_id, instance_id=0)
                )
                self.assertEqual(opcode, 13664)
                count, identity, prototype, size = struct.unpack_from(">hqqH", body)
                self.assertEqual((count, identity, prototype), (1, source_id, 19825))
                self.assertEqual(body[20 : 20 + size], gateway.appearance(row, binding))
                activation = gateway.activation(
                    dict(map_id=map_id, instance_id=0),
                    struct.pack(">qHH", source_id, 0, 0),
                )
                self.assertEqual(
                    struct.unpack(">qiBi", activation["body"]),
                    (source_id, binding["destination"]["destination_id"], 0, 2),
                )

    def test_wrong_uid_map_private_scope_and_action_cannot_select_a_route(self):
        actor = dict(map_id=472, instance_id=0)
        self.assertIsNone(gateway.activation(actor, struct.pack(">qHH", 999999, 0, 0)))
        self.assertIsNone(
            gateway.activation(
                dict(map_id=527, instance_id=0), struct.pack(">qHH", 17452, 0, 0)
            )
        )
        for action, padding, instance in ((1, 0, 0), (0, 1, 0), (0, 0, 99)):
            with self.subTest(action=action, padding=padding, instance=instance):
                with self.assertRaises(ValueError):
                    gateway.activation(
                        dict(actor, instance_id=instance),
                        struct.pack(">qHH", 17452, action, padding),
                    )
        self.assertIsNone(
            gateway.attachment(self.row(472, 17452), dict(map_id=472, instance_id=99))
        )
        with patch.object(dungeon_instances, "_ROUTES", {}):
            self.assertIsNone(
                gateway.activation(actor, struct.pack(">qHH", 17452, 0, 0))
            )

    def test_first_attachment_replay_unload_and_map_reset_have_one_gateway(self):
        map_id, identity = 472, 17452
        row = self.row(map_id, identity)
        scope = dict(
            session_id="peer",
            generation="lease",
            account_id=1,
            character_id=2,
            map_id=map_id,
            instance_id=0,
        )
        tracker = InteractivePublication(
            lambda _: (row,), attachment_projector=gateway.attachment
        )
        loader = frame(12318, struct.pack(">ii", int(row["x"]), int(row["y"])))
        state = world_static._DUNGEON_ENTRY_STATE
        snapshot = frame(13984, struct.pack(">hqH", 1, identity, len(state)) + state)
        first = packets(tracker.transform(loader + snapshot, scope))
        self.assertEqual([opcode for opcode, _ in first], [12318, 13664])
        replay = packets(tracker.transform(snapshot, scope))
        self.assertEqual([opcode for opcode, _ in replay], [12344])
        tracker.transform(frame(12318, struct.pack(">ii", 1000, 1000)), scope)
        again = packets(tracker.transform(loader + snapshot, scope))
        self.assertEqual([opcode for opcode, _ in again], [12318, 13664])
        reset = packets(tracker.transform(frame(13256) + loader + snapshot, scope))
        self.assertEqual([opcode for opcode, _ in reset], [13256, 12318, 13664])
        self.assertEqual(first[-1][1], again[-1][1])
        self.assertEqual(tracker.attached, {identity})

    def test_projection_failure_does_not_commit_attachment_state(self):
        row = self.row(472, 17452)
        tracker = InteractivePublication(
            lambda _: (row,),
            attachment_projector=lambda *_: (_ for _ in ()).throw(
                ValueError("changed source")
            ),
        )
        scope = dict(
            session_id="peer",
            generation="lease",
            account_id=1,
            map_id=472,
            instance_id=0,
        )
        loader = frame(12318, struct.pack(">ii", -26, -21))
        state = world_static._DUNGEON_ENTRY_STATE
        snapshot = frame(13984, struct.pack(">hqH", 1, 17452, len(state)) + state)
        with self.assertRaises(ValueError):
            tracker.transform(loader + snapshot, scope)
        self.assertEqual(tracker.attached, set())
        self.assertIsNone(tracker.identity)
