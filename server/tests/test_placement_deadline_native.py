import unittest
from types import SimpleNamespace

from wakfu_server.placement_deadline import Deadline


class NativePlacementDeadlineTests(unittest.TestCase):
    def test_captured_ten_minute_placement_expires_at_its_native_boundary(self):
        deadline = Deadline()
        deadline.start(7, 600000, 10.0, native=True)
        fight = SimpleNamespace(id=7, phase="placement")
        self.assertFalse(deadline.take_expired(fight, 609.99))
        self.assertTrue(deadline.take_expired(fight, 610.0))
        self.assertFalse(deadline.take_expired(fight, 611.0))

    def test_ordinary_cap_and_invalid_native_durations_remain_rejected(self):
        deadline = Deadline()
        with self.assertRaises(ValueError):
            deadline.start(7, 600000, 10.0)
        with self.assertRaises(ValueError):
            deadline.start(7, 600001, 10.0, native=True)
        with self.assertRaises(ValueError):
            deadline.start(7, 600000, 10.0, native=1)
        deadline.start(7, 300000, 10.0)
        self.assertEqual(deadline.until, 310.0)


if __name__ == "__main__":
    unittest.main()
