"""Native loaded-neighborhood static snapshots, without attachment dedup."""
import struct
import unittest
from unittest.mock import patch

from wakfu_server import dungeon_instances, world_scene_sync, world_static


def states(bodies):
    rows = {}
    for body in bodies:
        count = struct.unpack_from(">h", body)[0]
        cursor = 2
        for _ in range(count):
            identity, size = struct.unpack_from(">qH", body, cursor)
            cursor += 10
            rows[identity] = body[cursor : cursor + size]
            cursor += size
        assert cursor == len(body)
    return rows


class WorldStaticScopeTests(unittest.TestCase):
    def test_reproduced_distant_definition_is_excluded_but_nearby_chest_remains(self):
        # Actual 2026-10-11 log: map1134 actor(-18,-134), failed34643(17,-50).
        position = dict(x=-18, y=-134, z=50)
        scoped = states(world_static.snapshots(1134, position=position))
        self.assertNotIn(34643, scoped)
        self.assertIn(34643, states(world_static.snapshots(1134)))
        nearby = states(world_static.snapshots(1134, position=dict(x=-7, y=-108, z=30)))
        self.assertIn(31687, nearby)
        self.assertEqual(nearby[31687], world_static._DYNAMIC_STATES[(1134, 31687)])

    def test_every_catalog_object_is_available_from_its_own_native_partition(self):
        # Check the complete catalog's spatial contract, independently of type.
        for map_id in world_static._MAPS:
            rows = world_static.objects(map_id)
            partitions = {world_scene_sync.chunk((row["x"], row["y"])) for row in rows}
            for center in partitions:
                position = (center[0] * 18, center[1] * 18, 0)
                scoped = states(world_static.snapshots(map_id, position=position))
                expected = {
                    row["id"]
                    for row in rows
                    if world_scene_sync.chunk((row["x"], row["y"]))
                    in world_scene_sync.neighborhood(center)
                }
                self.assertEqual(set(scoped), expected, (map_id, center))

    def test_scope_ignores_altitude_and_retries_are_never_suppressed(self):
        first = world_static.snapshots(1134, position=dict(x=-7, y=-108, z=-300))
        self.assertTrue(states(first))
        second = world_static.snapshots(1134, position=dict(x=-7, y=-108, z=300))
        self.assertEqual(first, second)
        self.assertEqual(world_static.snapshots(1134, position=(-7, -108, 0)), first)

    def test_registered_entrance_override_and_nonentrance_native_states_are_preserved(
        self,
    ):
        with patch.object(
            dungeon_instances, "entry_object_ids", return_value=frozenset({26842})
        ):
            scoped = states(world_static.snapshots(527, position=(-245, -88, 0)))
        self.assertEqual(scoped[26842], world_static._DUNGEON_ENTRY_STATE)
        for identity, payload in scoped.items():
            if identity != 26842:
                self.assertEqual(payload, world_static._DYNAMIC_STATES[(527, identity)])

    def test_empty_map_or_partition_produces_no_fabricated_objects(self):
        self.assertEqual(
            states(world_static.snapshots(2147483647, position=(0, 0, 0))), {}
        )
        self.assertEqual(
            states(world_static.snapshots(1134, position=(1000000, 1000000, 0))), {}
        )


if __name__ == "__main__":
    unittest.main()
