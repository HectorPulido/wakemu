import unittest
from types import SimpleNamespace

from wakfu_server.combat_spell_commit import _states_lesson_presentation
from wakfu_server.combat_tactical_markers import _marker_packet
from wakfu_server.ecology_feedback import information
from wakfu_server.achievements.rii_states_contract import MESSAGES


class StatesPresentationTests(unittest.TestCase):
    def test_progress_packets_are_scoped_to_owner_and_transition(self):
        old = SimpleNamespace(
            rii_states_lesson_contract={"owner": 7, "hits": 0, "green": [2, 2, 0]}
        )
        contract = {"owner": 7, "hits": 1, "red": [1, 2, 0]}
        fight = SimpleNamespace(
            id=12, walkable={(1, 2, 0), (2, 2, 0)}, rii_states_lesson_contract=contract
        )
        marker = _marker_packet(12, (1, 2, 0), 7, 1, True)
        check = lambda packet: _states_lesson_presentation(
            fight, *packet, source_fight=old
        )
        self.assertTrue(check(marker))
        self.assertTrue(check(_marker_packet(12, (2, 2, 0), 7, 0, False)))
        self.assertFalse(check(_marker_packet(12, (1, 2, 0), 7, 0, False)))
        self.assertTrue(check(information(MESSAGES[1])))
        self.assertFalse(check(_marker_packet(12, (1, 2, 0), 8, 1, True)))
        self.assertFalse(check(information(MESSAGES[2])))
        self.assertFalse(check((12226, b"short")))
        contract["hits"] = 2
        self.assertFalse(check(marker))
        self.assertFalse(check(information(MESSAGES[2])))
