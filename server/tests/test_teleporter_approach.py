import unittest
from wakfu_server.movement import Movement
from wakfu_server.teleporter_approach import callback


class TeleporterApproachTests(unittest.TestCase):
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
