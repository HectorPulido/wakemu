"""Reconstructed Airyna acceptance must preserve unrelated progress."""
import unittest

from wakfu_server.achievements.rii_lesson_activation import plan


def definition():
    return {
        "d": 5143,
        "native_class": "aJM",
        "aqb": False,
        "cjI": "",
        "cjU": 0,
        "getDuration": 0,
        "cjJ": [{"d": x} for x in (10574, 10575, 10576, 10608, 10609, 10610, 10611)],
    }


def state():
    return {
        "running": [5160],
        "completed": [],
        "objectives": [10614],
        "tracking": [5160],
        "variables": {},
        "recent": [],
        "completion_dates": {},
    }


class LessonActivationTests(unittest.TestCase):
    def test_start_tracks_once_without_completing_lesson_or_hidden_flag(self):
        before = state()
        after, added = plan(before, definition())
        self.assertTrue(added)
        self.assertEqual(after["running"], [5143, 5160])
        self.assertEqual(after["tracking"], [5143, 5160])
        self.assertEqual(after["objectives"], [10614])
        self.assertEqual(before, state())
        self.assertEqual(plan(after, definition()), (after, False))

    def test_completed_quest_is_not_reset(self):
        before = state()
        before["completed"] = [5143]
        before["objectives"].append(10574)
        self.assertEqual(plan(before, definition()), (before, False))

    def test_changed_native_quest_is_rejected(self):
        native = definition()
        native["cjJ"].pop()
        with self.assertRaises(ValueError):
            plan(state(), native)


if __name__ == "__main__":
    unittest.main()
