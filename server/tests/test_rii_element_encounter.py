import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from wakfu_server.achievements import rii_element_encounter as encounter


class ElementalEncounterAuthorityTests(unittest.TestCase):
    def setUp(self):
        self.monster = {"id": -30, "ref": 5466}
        self.fight = SimpleNamespace()
        self.db = Mock()

    def test_bind_requires_exact_owned_receipt(self):
        self.db.execute.return_value.fetchone.return_value = {
            "payload": encounter._payload(7, -30)
        }
        self.assertTrue(encounter.bind(self.db, self.fight, 7, [self.monster]))
        self.assertEqual(
            self.fight.rii_element_lesson_contract,
            {"owner": 7, "target": -30, "hits": 0, "last_turn": None},
        )
        self.db.execute.return_value.fetchone.return_value = {
            "payload": encounter._payload(8, -30)
        }
        self.assertFalse(encounter.bind(self.db, SimpleNamespace(), 7, [self.monster]))

    def test_other_player_cannot_take_owned_sack(self):
        self.db.execute.return_value.fetchall.return_value = [
            {"character_id": 7, "payload": encounter._payload(7, -30)}
        ]
        self.assertTrue(encounter.admit(self.db, 7, [self.monster]))
        with self.assertRaises(ValueError):
            encounter.admit(self.db, 8, [self.monster])

    def test_settlement_requires_four_hits_and_matching_victory(self):
        fight = SimpleNamespace(
            id=10,
            phase="finished",
            winner=0,
            actors={7: SimpleNamespace(team=0), -30: SimpleNamespace(team=1)},
            rii_element_lesson_contract={"owner": 7, "target": -30, "hits": 3},
        )
        self.assertEqual(
            encounter.settle_participants(self.db, Mock(), fight, [], [self.monster]),
            {},
        )
        fight.rii_element_lesson_contract["hits"] = 4
        fight.winner = 1
        self.assertEqual(
            encounter.settle_participants(self.db, Mock(), fight, [], [self.monster]),
            {},
        )
        self.db.execute.assert_not_called()


if __name__ == "__main__":
    unittest.main()
