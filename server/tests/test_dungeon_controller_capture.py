"""Check the native scenario dispatch contract used for controller evidence."""
import struct
import unittest
from server.tools.audit_dungeon_controller_capture import decode_scenario_dispatch


class DungeonControllerCaptureTests(unittest.TestCase):
    def test_native_order_is_event_then_scenario_then_arguments(self):
        result = decode_scenario_dispatch(struct.pack(">Biibq", 0, 21866, 2501, 1, 5))
        self.assertEqual(result["scenario_id"], 2501)
        self.assertEqual(result["event_id"], 21866)
        self.assertEqual(result["function"], "event_2501_21866")
        self.assertEqual(result["arguments"], [5])

    def test_negative_scenario_function_replaces_hyphen_like_client(self):
        result = decode_scenario_dispatch(struct.pack(">Biib", 1, 1842, -1087, 0))
        self.assertEqual(result["function"], "reward__1087_1842")

    def test_malformed_payloads_do_not_become_controller_evidence(self):
        for body in [
            b"",
            struct.pack(">Biib", 0, 1, 2, -1),
            struct.pack(">Biib", 0, 1, 2, 1),
            struct.pack(">Biib", 0, 1, 2, 0) + b"x",
        ]:
            with self.subTest(body=body):
                with self.assertRaises(ValueError):
                    decode_scenario_dispatch(body)


if __name__ == "__main__":
    unittest.main()
