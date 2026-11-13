import unittest
from unittest.mock import Mock
from wakfu_server.achievements import flat_xp


class FlatXpTest(unittest.TestCase):
    def test_rates_and_invalid_values(self):
        self.assertEqual(flat_xp.scaled(445000, 100000), 4450000)
        self.assertEqual(flat_xp.scaled(445000, 10000), 445000)
        self.assertEqual(flat_xp.scaled(445000, 0), 0)
        for base, rate in [(True, 10000), (1, -1), (0, 10000)]:
            with self.assertRaises(ValueError):
                flat_xp.scaled(base, rate)

    def test_frozen_amount_survives_rate_changes_and_legacy_is_preserved(self):
        reward = {"d": 2069, "aeV": 6, "ckl": [445000]}
        ent = {
            "achievement_id": 1217,
            "cycle_key": "once",
            "reward_key": "2069",
            "payload": reward,
        }
        db = Mock()
        db.execute.return_value.fetchone.return_value = {
            "base_xp": 445000,
            "xp_rate_bp": 100000,
            "awarded_xp": 4450000,
        }
        self.assertEqual(flat_xp.amount(db, {"id": 16}, reward, ent), 4450000)
        db.execute.return_value.fetchone.return_value = None
        self.assertEqual(flat_xp.amount(db, {"id": 16}, reward, ent), 445000)
        db.execute.return_value.fetchone.return_value = {
            "base_xp": 445000,
            "xp_rate_bp": 100000,
            "awarded_xp": 4450001,
        }
        with self.assertRaises(ValueError):
            flat_xp.amount(db, {"id": 16}, reward, ent)


if __name__ == "__main__":
    unittest.main()
