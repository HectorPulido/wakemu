import struct, unittest
from wakfu_server.combat_phase import action_transition


class PhaseTests(unittest.TestCase):
    def test_native_verified_fixture(self):
        opcode, body = action_transition(91, timestamp_ms=123456)
        self.assertEqual(opcode, 12514)
        self.assertEqual(len(body), 49)
        self.assertEqual(struct.unpack_from(">iBiq", body), (91, 2, 0, 123456))
        self.assertEqual(body[21:28], struct.pack(">iBBB", 3, 0, 0, 0))
        self.assertEqual(body[33:43], bytes(10))
        self.assertEqual(body[-2:], bytes(2))

    def test_invalid_identity(self):
        with self.assertRaises(ValueError):
            action_transition(0)

    def test_forbids_zero_bonus_period(self):
        with self.assertRaises(ValueError):
            action_transition(91, bonus_period=0)
