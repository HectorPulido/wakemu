import struct
import unittest
from types import SimpleNamespace

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


if __name__ == "__main__":
    unittest.main()
