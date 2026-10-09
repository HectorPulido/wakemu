import unittest
from wakfu_server.movement import Movement
from wakfu_server.teleporter_approach import callback


class TeleporterApproachTests(unittest.TestCase):
    def test_private_instance_is_bound_to_its_approved_path(self):
        movement = Movement({"x": 4, "y": 6, "z": 2})
        allowed = callback(movement, map_id=1086, instance_id=144115188075855873)
        character = {"map_id": 1086, "instance_id": 144115188075855873}
        source = {"map_id": 1086, "x": 4, "y": 6}
        self.assertTrue(allowed(character, source))
        self.assertFalse(allowed({**character, "instance_id": 0}, source))
        self.assertFalse(
            allowed({**character, "instance_id": 144115188075855874}, source)
        )
        self.assertFalse(allowed({**character, "map_id": 527}, source))
        self.assertFalse(allowed(character, {**source, "map_id": 527}))
        self.assertFalse(allowed(character, {**source, "x": 5}))

    def test_exact_native_xy_and_no_invented_adjacent_radius(self):
        movement = Movement({"x": 4, "y": 6, "z": 2})
        allowed = callback(movement, map_id=1134)
        character = {"map_id": 1134, "instance_id": 0, "x": 4, "y": 6, "z": 2}
        self.assertTrue(allowed(character, {"map_id": 1134, "x": 4, "y": 6, "z": 2}))
        self.assertFalse(allowed(character, {"map_id": 1134, "x": 5, "y": 6, "z": 2}))
        self.assertFalse(
            allowed({**character, "map_id": 527}, {"map_id": 1134, "x": 4, "y": 6})
        )
        self.assertFalse(
            allowed({**character, "instance_id": 9}, {"map_id": 1134, "x": 4, "y": 6})
        )

    def test_source_on_approved_path_not_only_animated_endpoint(self):
        movement = Movement({"x": 4, "y": 6, "z": 2})
        points = movement.validate(
            {
                "start_position": {"x": 4, "y": 6, "z": 2},
                "steps": [{"dx": 1, "dy": 0, "dz": 0}, {"dx": 1, "dy": 0, "dz": 0}],
                "end_position": {"x": 6, "y": 6, "z": 2},
            }
        )
        movement.commit(points)
        allowed = callback(movement, map_id=1134)
        self.assertTrue(
            allowed(
                {"map_id": 1134, "instance_id": 0}, {"map_id": 1134, "x": 5, "y": 6}
            )
        )
        movement.commit({(6, 6, 2)})
        self.assertFalse(
            allowed(
                {"map_id": 1134, "instance_id": 0}, {"map_id": 1134, "x": 5, "y": 6}
            )
        )

    def test_native_entry_mask_uses_walkable_neighbor_and_exact_height(self):
        source = {
            "map_id": 527,
            "x": -245,
            "y": -90,
            "z": 0,
            "approach_mask": 1,
            "approach_orientation": 3,
            "approach_positions": [{"x": -245, "y": -89, "z": 0}],
        }
        movement = Movement({"x": -245, "y": -89, "z": 0})
        allowed = callback(movement, map_id=527)
        character = {"map_id": 527}
        self.assertTrue(allowed(character, source))
        movement.commit({(-245, -90, 0), (-244, -89, 0), (-245, -89, 1)})
        self.assertFalse(allowed(character, source))
        self.assertFalse(allowed(character, {**source, "approach_orientation": 8}))
        self.assertFalse(allowed(character, {**source, "approach_mask": -1}))
        self.assertFalse(allowed(character, {**source, "approach_mask": True}))
        self.assertFalse(allowed(character, {**source, "approach_orientation": False}))
        movement.commit(set())
        self.assertTrue(allowed({**character, "x": -245, "y": -89, "z": 0}, source))
        self.assertFalse(allowed({**character, "x": -245, "y": -90, "z": 0}, source))

    def test_zero_mask_direct_action_requires_exact_owned_xy(self):
        movement = Movement({"x": 4, "y": 6, "z": 2})
        movement.commit(set())
        allowed = callback(movement, map_id=1086, instance_id=9)
        source = {"map_id": 1086, "x": 4, "y": 6, "approach_mask": 0}
        character = {"map_id": 1086, "instance_id": 9, "x": 4, "y": 6, "z": 2}
        self.assertTrue(allowed(character, source))
        self.assertFalse(allowed({**character, "x": 5}, source))
        self.assertFalse(allowed({**character, "instance_id": 0}, source))
