"""Artifact-enabled exploration uses the existing packed movement contract."""
import struct
import unittest
from protocol_codec import decode_body
from wakfu_server.movement import Movement
from wakfu_server.wire import movement_path


class ExplorationMovementWireTests(unittest.TestCase):
    def test_four_height_stairs_survive_request_validation_and_remote_relay(self):
        body = struct.pack(">iiihB", 1, 15, -31, -2, 2) + bytes(
            [(7 << 5) | ((-4) & 31), (7 << 5) | ((-2) & 31)]
        )
        request = decode_body("out", 13331, body)
        route = Movement(request["start_position"])
        route.commit(route.validate(request))
        remote = decode_body("in", 13852, movement_path(42, body))
        self.assertEqual(remote["end_position"], dict(x=15, y=-33, z=-8))
        self.assertEqual([s["dz"] for s in remote["steps"]], [-4, -2])
        self.assertEqual(remote["steps"], request["steps"])
        self.assertIn((15, -32, -6), route.approved)

    def test_climb_and_descent_keep_signed_height(self):
        body = struct.pack(">iiihB", 1, 0, 0, 0, 2) + bytes(
            [(1 << 5) | 7, (1 << 5) | ((-7) & 31)]
        )
        request = decode_body("out", 13331, body)
        route = Movement(request["start_position"])
        route.validate(request)
        self.assertEqual(
            decode_body("in", 13852, movement_path(8, body))["end_position"],
            dict(x=2, y=0, z=0),
        )

    def test_redirect_after_jump_requires_previously_approved_origin(self):
        body = struct.pack(">iiihB", 1, 0, 0, 0, 1) + bytes([(1 << 5) | 4])
        request = decode_body("out", 13331, body)
        route = Movement(request["start_position"])
        route.commit(route.validate(request))
        request["start_position"] = dict(x=99, y=0, z=0)
        request["end_position"] = dict(x=100, y=0, z=4)
        with self.assertRaisesRegex(ValueError, "previous approved path"):
            route.validate(request)

    def test_truncated_and_trailing_path_bytes_rejected(self):
        body = struct.pack(">iiihB", 1, 0, 0, 0, 1) + bytes([(1 << 5) | 4])
        for malformed in (body[:-1], body + b"\0"):
            with self.assertRaises(ValueError):
                movement_path(42, malformed)


if __name__ == "__main__":
    unittest.main()
