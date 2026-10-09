import struct
import unittest
from unittest.mock import patch
from types import SimpleNamespace
from wakfu_server import world_static
from wakfu_server import dungeon_instances


class WorldStaticTests(unittest.TestCase):
    def snapshot_payloads(self, map_id):
        actual = {}
        for body in world_static.snapshots(map_id):
            count = struct.unpack_from(">h", body)[0]
            cursor = 2
            for _ in range(count):
                identity, length = struct.unpack_from(">qh", body, cursor)
                cursor += 10
                actual[identity] = body[cursor : cursor + length]
                cursor += length
            self.assertEqual(cursor, len(body))
        return actual

    def test_registered_entrances_use_exact_official_dynamic_state(self):
        expected = bytes.fromhex("01020000000602000101010000010000000000")
        for configured in dungeon_instances._ROUTES.values():
            with self.subTest(route=configured.key):
                payloads = self.snapshot_payloads(configured.entry_map_id)
                self.assertEqual(payloads[configured.entry_object_id], expected)
                entrances = dungeon_instances.entry_object_ids(configured.entry_map_id)
                for row in world_static.objects(configured.entry_map_id):
                    if row["id"] not in entrances:
                        self.assertEqual(
                            payloads[row["id"]],
                            world_static._DYNAMIC_STATES[
                                (configured.entry_map_id, row["id"])
                            ],
                        )

    def test_every_native_object_hydrates_in_first_attachment_on_every_replay(self):
        with patch.object(dungeon_instances, "_ROUTES", {}):
            for map_id, indexed in world_static._MAPS.items():
                rows = tuple(indexed.values())
                with self.subTest(map_id=map_id):
                    bodies = world_static.snapshots(map_id)
                    self.assertEqual(bodies, world_static.snapshots(map_id))
                    payloads = self.snapshot_payloads(map_id)
                    for row in rows:
                        expected = world_static._DYNAMIC_STATES[(map_id, row["id"])]
                        self.assertEqual(payloads[row["id"]], expected)
                    # Never attach an unhydrated baseline before dynamic state.
                    self.assertEqual(len(bodies), (len(rows) + 32766) // 32767)
                    self.assertNotEqual(
                        bodies[0], world_static._snapshot_bodies(rows)[0]
                    )

    def test_catalog_covers_all_types_and_preserves_hidden_disabled_and_other_states(
        self,
    ):
        rows = [
            row for indexed in world_static._MAPS.values() for row in indexed.values()
        ]
        self.assertEqual(len(world_static._DYNAMIC_STATES), len(rows))
        self.assertEqual(
            {row["type"] for row in rows},
            {row["type"] for row in world_static._STATE_CATALOG["objects"]},
        )
        decoded = []
        for key, payload in world_static._DYNAMIC_STATES.items():
            self.assertEqual(payload[:7], bytes.fromhex("01020000000602"))
            state, visible, usable, bj, bk, bh, extra, count = struct.unpack_from(
                ">h6Bi", payload, 7
            )
            self.assertEqual(len(payload), 19 + count)
            self.assertTrue(
                all(flag in (0, 1) for flag in (visible, usable, bj, bk, bh))
            )
            decoded.append((state, visible, usable))
        self.assertTrue(any(not visible for _, visible, _ in decoded))
        self.assertTrue(any(visible and not usable for _, visible, usable in decoded))
        self.assertTrue(any(state != 1 for state, _, _ in decoded))

    def test_official_capture_vectors_match_native_decoder_states(self):
        for map_id, identity, expected in (
            (527, 26865, "01020000000602000101010000000000000000"),
            (527, 26878, "01020000000602000101010000010000000000"),
            (527, 26842, "01020000000602000101010000010000000000"),
            (1134, 31514, "01020000000602000101010000000000000000"),
        ):
            self.assertEqual(
                world_static._DYNAMIC_STATES[(map_id, identity)].hex(), expected
            )

    def test_registry_reload_is_observed_without_mutating_baseline(self):
        original = world_static.objects(527)
        empty = {}
        installed = {"entry": SimpleNamespace(entry_map_id=527, entry_object_id=26842)}
        with patch.object(dungeon_instances, "_ROUTES", empty):
            baseline = self.snapshot_payloads(527)[26842]
        with patch.object(dungeon_instances, "_ROUTES", installed):
            first = self.snapshot_payloads(527)
            self.assertEqual(first, self.snapshot_payloads(527))
            self.assertEqual(first[26842], world_static._DUNGEON_ENTRY_STATE)
        with patch.object(dungeon_instances, "_ROUTES", empty):
            self.assertEqual(self.snapshot_payloads(527)[26842], baseline)
        self.assertEqual(world_static.objects(527), original)

    def test_snapshot_roundtrip_preserves_every_installed_object(self):
        expected = {
            row["id"]: world_static._DYNAMIC_STATES[(1134, row["id"])]
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
