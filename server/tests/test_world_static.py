import struct
import unittest
from wakfu_server import world_static


class WorldStaticTests(unittest.TestCase):
    def test_snapshot_roundtrip_preserves_every_installed_object(self):
        expected = {
            row["id"]: bytes.fromhex(row["payload_hex"])
            for row in world_static.objects(1134)
        }
        actual = {}
        for body in world_static.snapshots(1134):
            (count,) = struct.unpack_from(">h", body)
            cursor = 2
            for _ in range(count):
                identity, length = struct.unpack_from(">qh", body, cursor)
                cursor += 10
                actual[identity] = body[cursor : cursor + length]
                cursor += length
            self.assertEqual(cursor, len(body))
        self.assertEqual(actual, expected)
        self.assertTrue(any(r["type"] == "Door" for r in world_static.objects(527)))

    def test_transport_activate_is_distinct_from_registration(self):
        character = {"map_id": 1134, "instance_id": 0}
        for action, route in ((0, "transport_menu"), (24, "transport_registration")):
            result = world_static.interaction(
                character, struct.pack(">qHH", 31333, action, 0)
            )
            self.assertEqual(result["type"], "Drago")
            self.assertEqual(result["route"], route)
        with self.assertRaises(ValueError):
            world_static.interaction(
                {"map_id": 527, "instance_id": 0}, struct.pack(">qHH", 31333, 24, 0)
            )
        with self.assertRaises(ValueError):
            world_static.interaction(
                {"map_id": 1134, "instance_id": 1}, struct.pack(">qHH", 31333, 24, 0)
            )

    def test_catalog_return_cannot_mutate_baseline(self):
        rows = world_static.objects(1134)
        identity = rows[0]["id"]
        rows[0]["type"] = "corrupted"
        self.assertNotEqual(
            next(r for r in world_static.objects(1134) if r["id"] == identity)["type"],
            "corrupted",
        )
