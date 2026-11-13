import unittest
from types import SimpleNamespace

from wakfu_server.combat_spell_commit import _movement_lesson_presentation
from wakfu_server.combat_tactical_markers import _marker_packet
from wakfu_server.ecology_feedback import information


class MovementSpellDeliveryTests(unittest.TestCase):
    def test_only_owned_lesson_marker_and_notice_are_admitted(self):
        fight = SimpleNamespace(
            id=10,
            walkable={(1, 2, 0)},
            rii_movement_lesson_contract={"owner": 7, "marker": [1, 2, 0]},
        )
        self.assertTrue(
            _movement_lesson_presentation(
                fight, *_marker_packet(10, (1, 2, 0), 7, 0, True)
            )
        )
        self.assertTrue(
            _movement_lesson_presentation(
                fight, *information("Movement lesson: move the sack to cell (1, 2).")
            )
        )
        self.assertFalse(
            _movement_lesson_presentation(
                fight, *_marker_packet(10, (1, 2, 0), 8, 0, True)
            )
        )
        self.assertFalse(
            _movement_lesson_presentation(fight, *information("Unrelated message"))
        )
        self.assertFalse(
            _movement_lesson_presentation(
                SimpleNamespace(id=10), *_marker_packet(10, (1, 2, 0), 7, 0, True)
            )
        )

    def test_only_old_marker_can_be_removed_and_new_marker_added(self):
        before = SimpleNamespace(
            id=10,
            walkable={(1, 2, 0), (2, 2, 0), (3, 2, 0)},
            rii_movement_lesson_contract={"owner": 7, "marker": [1, 2, 0]},
        )
        after = SimpleNamespace(
            id=10,
            walkable=before.walkable,
            rii_movement_lesson_contract={"owner": 7, "marker": [2, 2, 0]},
        )
        check = lambda packet: _movement_lesson_presentation(
            after, *packet, source_fight=before
        )
        self.assertTrue(check(_marker_packet(10, (1, 2, 0), 7, 0, False)))
        self.assertTrue(check(_marker_packet(10, (2, 2, 0), 7, 0, True)))
        self.assertFalse(check(_marker_packet(10, (3, 2, 0), 7, 0, True)))
        self.assertFalse(check(_marker_packet(10, (2, 2, 0), 7, 0, False)))
        self.assertFalse(check(_marker_packet(11, (2, 2, 0), 7, 0, True)))
        self.assertFalse(check(_marker_packet(10, (2, 2, 0), 7, 1, True)))
        self.assertFalse(
            check(information("Movement lesson: move the sack to cell (1, 2)."))
        )
        before.rii_movement_lesson_contract["owner"] = 8
        self.assertFalse(check(_marker_packet(10, (2, 2, 0), 7, 0, True)))
