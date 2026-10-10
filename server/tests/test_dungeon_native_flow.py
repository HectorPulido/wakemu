"""Native object room binding and teleport exploration preserve physical contracts."""
import copy
import unittest
from wakfu_server import dungeon_native_flow as native


class NativeDungeonFlowTests(unittest.TestCase):
    def setUp(self):
        self.topology = dict(
            policy=native.TELEPORT_POLICY,
            asset_map_id=7,
            rooms=[
                dict(order=1, cells=[[0, 0, 0], [1, 0, 0]]),
                dict(order=2, cells=[[10, 0, 0]]),
            ],
            physical_doors=[],
            doors=[
                dict(
                    source_id=20,
                    source_room=1,
                    destination_room=2,
                    source_position=[2, 0, 0],
                    native_approach_cells=[[1, 0, 0]],
                )
            ],
            physical_exit_objects=[],
            exploration_geometry=dict(
                cells=[[0, 0, 0], [1, 0, 0], [10, 0, 0]],
                edges=[[[0, 0, 0], [1, 0, 0]], [[1, 0, 0], [0, 0, 0]]],
            ),
        )
        self.source = dict(
            id=20,
            map_id=7,
            x=2,
            y=0,
            z=0,
            approach_blocks_center=True,
            approach_positions=[dict(x=1, y=0, z=0)],
        )

    def test_blocking_center_uses_literal_approach_binding_without_adding_cells(self):
        before = copy.deepcopy(self.topology["rooms"])
        self.assertEqual(native.object_room(self.topology, self.source), 1)
        self.assertEqual(self.topology["rooms"], before)

    def test_invented_approach_and_wrong_room_binding_fail_closed(self):
        for approaches in ([[0, 0, 0]], [[10, 0, 0]], []):
            topology = copy.deepcopy(self.topology)
            topology["doors"][0]["native_approach_cells"] = approaches
            with self.subTest(approaches=approaches), self.assertRaises(ValueError):
                native.object_room(topology, self.source)

    def test_conflicting_native_center_room_is_rejected(self):
        topology = copy.deepcopy(self.topology)
        topology["rooms"][1]["cells"].append([2, 0, 0])
        with self.assertRaises(ValueError):
            native.object_room(topology, self.source)

    def test_ordinary_walk_in_room_and_locked_teleport_region_are_separate(self):
        request = dict(
            start_position=dict(x=0, y=0, z=0),
            end_position=dict(x=1, y=0, z=0),
            steps=[dict(dx=1, dy=0, dz=0)],
        )
        self.assertEqual(
            native.validate_movement(self.topology, request, unlocked_room=1), (1, 0, 0)
        )
        request = dict(
            start_position=dict(x=10, y=0, z=0),
            end_position=dict(x=10, y=0, z=0),
            steps=[],
        )
        with self.assertRaises(ValueError):
            native.validate_movement(self.topology, request, unlocked_room=1)
        self.assertEqual(
            native.validate_movement(self.topology, request, unlocked_room=2),
            (10, 0, 0),
        )

    def test_wrong_asset_map_and_unknown_policy_are_rejected(self):
        with self.assertRaises(ValueError):
            native.object_room(self.topology, dict(self.source, map_id=8))
        self.assertFalse(native.enabled(dict(policy="unknown")))
