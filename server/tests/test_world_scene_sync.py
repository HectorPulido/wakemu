import struct
import unittest
from unittest.mock import patch
from wakfu_server import world_scene_sync, world_static, dungeon_instances


def decode(bodies):
    rows = {}
    for body in bodies:
        count = struct.unpack_from(">h", body)[0]
        cursor = 2
        for _ in range(count):
            identity, size = struct.unpack_from(">qh", body, cursor)
            cursor += 10
            rows[identity] = body[cursor : cursor + size]
            cursor += size
        assert cursor == len(body)
    return rows


class SceneSyncTests(unittest.TestCase):
    def test_refresh_snapshots_preserves_all_records_and_native_layout(self):
        rows = ((26865, b"first"), (26878, b"second"))
        body = struct.pack(">h", len(rows)) + b"".join(
            struct.pack(">qH", identity, len(payload)) + payload
            for identity, payload in rows
        )
        self.assertEqual(
            world_scene_sync.refresh_snapshots(body),
            tuple(
                struct.pack(">qH", identity, len(payload)) + payload
                for identity, payload in rows
            ),
        )
        self.assertEqual(world_scene_sync.refresh_snapshots(b"\x00\x00"), ())

    def test_refresh_snapshots_rejects_malformed_entire_batches(self):
        valid = struct.pack(">hqH", 1, 26865, 3) + b"abc"
        malformed = [
            b"",
            b"\x00",
            b"\xff\xff",
            valid[:-1],
            valid + b"x",
            struct.pack(">hqH", 1, 26865, 0),
            struct.pack(">hqH", 2, 26865, 3) + b"abc",
            struct.pack(">hqH", 1, 26865, 65535) + b"a",
        ]
        for body in malformed:
            with self.subTest(body=body), self.assertRaises(ValueError):
                world_scene_sync.refresh_snapshots(body)

    def test_negative_chunk_boundaries_match_native_floor(self):
        for x, expected in ((-19, -2), (-18, -1), (-1, -1), (0, 0), (17, 0), (18, 1)):
            self.assertEqual(world_scene_sync.chunk((x, x)), (expected, expected))
        self.assertEqual(len(world_scene_sync.neighborhood((0, 0))), 9)

    def test_selected_regions_have_only_dynamic_payloads(self):
        regions = world_scene_sync.neighborhood((-13, -3))
        actual = decode(world_scene_sync.dynamic_snapshots(527, regions))
        expected = {
            row["id"]
            for row in world_static.objects(527)
            if world_scene_sync.chunk((row["x"], row["y"])) in regions
        }
        self.assertEqual(set(actual), expected)
        self.assertTrue(actual)
        self.assertTrue(
            all(
                payload.startswith(bytes.fromhex("01020000000602"))
                for payload in actual.values()
            )
        )
        self.assertNotIn(
            26842, actual
        )  # Dungeon entrance is outside this neighborhood.

    def test_updates_wait_for_walk_and_stop_after_tail(self):
        sync = world_scene_sync.SceneSync()
        sync.arm(527, 0, [(-219, -40, 0)], 10)
        self.assertEqual(sync.poll(527, 0, 10.99), ())
        self.assertTrue(sync.poll(527, 0, 11))
        self.assertTrue(sync.poll(527, 0, 14))
        self.assertEqual(sync.pending, {})
        self.assertEqual(sync.poll(527, 0, 1000), ())

    def test_route_registration_is_read_when_hydrating(self):
        with patch.object(
            dungeon_instances, "entry_object_ids", return_value=frozenset((26842,))
        ):
            rows = decode(world_scene_sync.dynamic_snapshots(527, {(-14, -5)}))
        self.assertEqual(rows[26842], world_static._DUNGEON_ENTRY_STATE)

    def test_map_and_instance_changes_discard_previous_schedule(self):
        sync = world_scene_sync.SceneSync()
        sync.arm(527, 1, [(-219, -40, 0)], 0)
        self.assertEqual(sync.poll(527, 2, 1), ())
        self.assertEqual(sync.pending, {})
        sync.arm(527, 1, [(-219, -40, 0)], 0)
        sync.arm(1134, 0, [(0, 0, 0)], 1)
        self.assertEqual(sync.identity, (1134, 0))
        self.assertTrue(
            all((-13, -3) not in regions for regions in sync.pending.values())
        )

    def test_redirect_keeps_only_relevant_outstanding_partitions(self):
        sync = world_scene_sync.SceneSync()
        sync.arm(527, 0, [(-219, -40, 0)], 0)
        sync.arm(527, 0, [(-245, -90, 0)], 0.1)
        relevant = world_scene_sync.neighborhood((-14, -5))
        self.assertTrue(all(regions <= relevant for regions in sync.pending.values()))

    def test_short_walk_retries_unacknowledged_overlapping_objects(self):
        sync = world_scene_sync.SceneSync()
        sync.arm(527, 0, [(-241, -84, 0), (-245, -88, 0)], 0)
        self.assertIn(26842, decode(sync.poll(527, 0, 1)))
        self.assertIn(26842, decode(sync.poll(527, 0, 3)))

    def test_destination_is_retried_before_conservative_travel_estimate(self):
        sync = world_scene_sync.SceneSync()
        sync.arm(527, 0, [(-219, -40, 0)] * 100 + [(-245, -89, 0)], 0)
        # Running may arrive sooner than the conservative walking estimate.
        self.assertIn(26842, decode(sync.poll(527, 0, 1)))

    def test_redirect_does_not_discard_a_due_update(self):
        sync = world_scene_sync.SceneSync()
        sync.arm(527, 0, [(-245, -88, 0)], 0)
        sync.arm(527, 0, [(-245, -88, 0), (-245, -89, 0)], 1.01)
        self.assertIn(26842, decode(sync.poll(527, 0, 1.01)))

    def test_rapid_redirects_keep_a_bounded_queue(self):
        sync = world_scene_sync.SceneSync()
        for index in range(1000):
            sync.arm(527, 0, [(-219, -40, 0), (-100, 50, 0)], index / 1000)
        self.assertLessEqual(len(sync.pending), 132)

    def test_unloaded_destination_receives_state_after_loading_and_return(self):
        sync = world_scene_sync.SceneSync()
        loaded = set()
        attached = {}

        def deliver(now):
            for identity, payload in decode(sync.poll(527, 0, now)).items():
                if identity in loaded:
                    attached[identity] = payload

        sync.arm(527, 0, [(-245, -89, 0)], 0)
        deliver(1)  # The native decoder drops packets before chunk registration.
        self.assertNotIn(26842, attached)
        loaded.add(26842)
        deliver(2)
        self.assertEqual(attached[26842], world_static._DUNGEON_ENTRY_STATE)
        loaded.clear()
        attached.clear()  # Native cdy unregisters objects on scene unload.
        sync.arm(527, 0, [(-219, -40, 0)], 10)
        deliver(14)
        self.assertNotIn(26842, attached)
        sync.arm(527, 0, [(-245, -89, 0)], 20)
        loaded.add(26842)
        deliver(21)
        self.assertEqual(attached[26842], world_static._DUNGEON_ENTRY_STATE)

    def test_maximum_path_has_finite_bounded_checkpoint_count(self):
        sync = world_scene_sync.SceneSync()
        sync.arm(527, 0, [(index, 0, 0) for index in range(256)], 0)
        self.assertLessEqual(len(sync.pending), 131)
        self.assertLessEqual(max(sync.pending), 131)
        self.assertTrue(all(len(regions) <= 18 for regions in sync.pending.values()))
        for steps in ([], [(0, 0)] * 257):
            with self.assertRaises(ValueError):
                sync.arm(527, 0, steps, 0)
