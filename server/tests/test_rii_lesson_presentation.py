import struct
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from wakfu_server.achievements import rii_lesson_presentation as presentation


class RiiLessonPresentationTests(unittest.TestCase):
    def test_each_official_lesson_starts_and_completes_its_own_scenario(self):
        for index, (contract, objective, start, end) in enumerate(presentation.LESSONS):
            with self.subTest(objective=objective):
                fight = SimpleNamespace(**{contract: {"owner": 1}})
                choice = (5756, 13260) if index == 0 else (5787, 13322 + index)
                self.assertEqual(
                    presentation.begin(*choice),
                    (13411, struct.pack(">BiiB", 0, start, 2543, 0)),
                )
                self.assertEqual(
                    presentation.admission(fight, 1, *choice),
                    presentation.begin(*choice),
                )
                with self.assertRaisesRegex(ValueError, "admitted owner"):
                    presentation.admission(fight, 2, *choice)
                wrong_choice = (5787, 13322 + (index + 1) % 7)
                with self.assertRaisesRegex(ValueError, "admitted owner"):
                    presentation.admission(fight, 1, *wrong_choice)
                self.assertIsNone(presentation.finish(fight, []))
                self.assertIsNone(
                    presentation.finish(
                        fight, [(13832, struct.pack(">qi", 1, objective + 1))]
                    )
                )
                self.assertEqual(
                    presentation.finish(
                        fight, [(13832, struct.pack(">qi", 1, objective))]
                    ),
                    (13411, struct.pack(">BiiB", 0, end, 2543, 0)),
                )

    def test_normal_fight_has_no_tutorial(self):
        self.assertIsNone(presentation.begin(1, 2))
        self.assertIsNone(presentation.finish(SimpleNamespace(), []))

    def test_staged_delivery_revision_repairs_old_claim_once_without_packet_changes(
        self,
    ):
        from wakfu_server.achievements import tutorial_presentation_once as once

        seen = set()

        def record(_db, character_id, key, _payload):
            identity = (character_id, key)
            fresh = identity not in seen
            seen.add(identity)
            return fresh

        with patch.object(once.storage, "record_event", side_effect=record):
            for index, (contract, _, start, _) in enumerate(presentation.LESSONS):
                fight = SimpleNamespace(**{contract: {"owner": 1}})
                choice = (5787, 13322 + index)
                packet = presentation.begin(*choice)
                self.assertTrue(once.claim(None, 1, 2543, start, 0))
                expected = [packet] if index >= 3 else []
                self.assertEqual(
                    presentation.claim_admission(None, fight, 1, *choice), expected
                )
                self.assertEqual(
                    presentation.claim_admission(None, fight, 1, *choice), []
                )
                if index >= 3:
                    self.assertIn((1, f"tutorial-presentation:2543:{start}:1"), seen)


if __name__ == "__main__":
    unittest.main()
