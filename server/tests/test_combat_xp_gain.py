import struct, unittest
from wakfu_server.combat_xp_gain import notification


class XpGainTests(unittest.TestCase):
    def reward(self):
        return dict(
            character={"id": 100},
            awarded=True,
            xp=103,
            xp_info=dict(won_xp=103, start_level=1, end_level=2, end_xp=103),
        )

    def test_native_delta_and_level_notification_is_suppressed_on_retry(self):
        reward = self.reward()
        self.assertEqual(
            notification(100, reward),
            (13613, struct.pack(">BBqqhB", 1, 1, 100, 103, 1, 0)),
        )
        reward["awarded"] = False
        self.assertIsNone(notification(100, reward))
        reward["awarded"] = True
        reward["xp"] = 0
        self.assertIsNone(notification(100, reward))

    def test_foreign_actor_and_mismatched_receipt_rejected(self):
        reward = self.reward()
        with self.assertRaises(ValueError):
            notification(999, reward)
        reward["xp_info"]["won_xp"] = 102
        with self.assertRaises(ValueError):
            notification(100, reward)
