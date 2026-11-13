import unittest

from wakfu_server.achievements.lesson_line_of_sight import observe


class LineOfSightLessonTests(unittest.TestCase):
    def setUp(self):
        self.event = dict(
            owner_id=1,
            target_id=-2,
            source_id=1,
            hit_target_id=-2,
            spell_id=7968,
            effect_reference=361213,
            source_xy=(0, 0),
            target_xy=(4, 0),
            damage=25,
            casting_los=True,
        )

    def test_only_four_authorized_hits_advance_without_mutating_source(self):
        state = {"hits": 0}
        for expected in range(1, 5):
            previous = state
            state = observe(state, **self.event)
            self.assertEqual(state, {"hits": expected})
            self.assertEqual(previous, {"hits": expected - 1})
        self.assertEqual(observe(state, **self.event), state)

    def test_blocked_wrong_owner_spell_effect_or_range_does_not_advance(self):
        for change in (
            {"casting_los": False},
            {"source_id": 3},
            {"hit_target_id": -3},
            {"spell_id": 7967},
            {"effect_reference": 361214},
            {"damage": 0},
            {"target_xy": (3, 0)},
        ):
            with self.subTest(change=change):
                self.assertEqual(
                    observe({"hits": 0}, **(self.event | change)), {"hits": 0}
                )

    def test_bad_ray_and_corrupt_counter_fail_closed(self):
        with self.assertRaises(ValueError):
            observe({"hits": 0}, **(self.event | {"casting_los": 1}))
        with self.assertRaises(ValueError):
            observe({"hits": 5}, **self.event)


if __name__ == "__main__":
    unittest.main()
