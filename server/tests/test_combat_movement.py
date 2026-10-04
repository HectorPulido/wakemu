import struct
import unittest
from wakfu_server.combat_movement import movement


class CombatMovementTests(unittest.TestCase):
    def test_native_decoder_fixture(self):
        opcode, body = movement(91, 2, -200, [(1, 2, 0), (2, 2, 1)], 3)
        self.assertEqual(opcode, 13624)
        self.assertEqual(
            body, struct.pack(">iiiqBBiihiih", 91, 2, -1, -200, 3, 0, 1, 2, 0, 2, 2, 1)
        )

    def test_requires_origin_and_destination(self):
        with self.assertRaises(ValueError):
            movement(1, 1, 1, [(0, 0, 0)], 0)

    def test_invalid_direction_and_height(self):
        with self.assertRaises(ValueError):
            movement(1, 1, 1, [(0, 0, 0), (1, 0, 0)], 8)
        with self.assertRaises(struct.error):
            movement(1, 1, 1, [(0, 0, 0), (1, 0, 32768)], 0)
