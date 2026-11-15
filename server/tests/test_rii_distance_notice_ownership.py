"""The distance lesson notice must belong to the cast that produced it."""

import unittest
from types import SimpleNamespace
from wakfu_server.combat.combat_spell_commit import _distance_lesson_presentation
from wakfu_server.ecology_feedback import information
from wakfu_server.achievements.rii_distance_contract import hint


class DistanceNoticeOwnershipTests(unittest.TestCase):
    def test_shared_contract_notice_is_accepted(self):
        contract = {"owner": 7, "target": -7, "hits": 1}
        fight = SimpleNamespace(id=562, rii_distance_lesson_contract=contract)
        packet = information(hint(1))
        self.assertTrue(
            _distance_lesson_presentation(fight, 349, packet[1], source_fight=fight)
        )

    def test_forged_or_stale_notice_is_rejected(self):
        live = SimpleNamespace(
            id=562, rii_distance_lesson_contract={"owner": 7, "target": -7, "hits": 0}
        )
        preview = SimpleNamespace(
            id=562, rii_distance_lesson_contract={"owner": 7, "target": -7, "hits": 3}
        )
        self.assertFalse(
            _distance_lesson_presentation(
                preview, 349, information(hint(3))[1], source_fight=live
            )
        )
        preview = SimpleNamespace(
            id=562, rii_distance_lesson_contract={"owner": 9, "target": -7, "hits": 1}
        )
        live = SimpleNamespace(
            id=562, rii_distance_lesson_contract={"owner": 7, "target": -7, "hits": 1}
        )
        self.assertFalse(
            _distance_lesson_presentation(
                preview, 349, information(hint(1))[1], source_fight=live
            )
        )


if __name__ == "__main__":
    unittest.main()
