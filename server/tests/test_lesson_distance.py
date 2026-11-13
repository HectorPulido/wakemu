import unittest

from wakfu_server.achievements.lesson_distance import observe
from wakfu_server.combat_conditions import UnknownCondition


def hit(state, *, distance=1, **overrides):
    event = dict(
        owner_id=7,
        target_id=-9,
        source_id=7,
        hit_target_id=-9,
        spell_id=7967,
        source_xy=(0, 0),
        target_xy=(distance, 0),
        damage=25,
    )
    event.update(overrides)
    return observe(state, **event)


class DistanceLessonTests(unittest.TestCase):
    def test_alternating_zones_require_four_qualified_hits(self):
        state = {"hits": 0}
        for distance in (1, 3, 2, 4):
            state = hit(state, distance=distance)
        self.assertEqual(state, {"hits": 4})
        self.assertEqual(hit(state, distance=1), state)

    def test_rejects_wrong_zone_identity_spell_and_zero_damage(self):
        state = {"hits": 0}
        for arguments in (
            {"distance": 3},
            {"source_id": 8},
            {"hit_target_id": -10},
            {"spell_id": 7968},
            {"damage": 0},
            {"distance": 0},
        ):
            self.assertEqual(hit(state, **arguments), state)
        self.assertEqual(state, {"hits": 0})
        state = hit(state, distance=2)
        self.assertEqual(hit(state, distance=2), state)

    def test_bad_state_and_coordinates_fail_closed(self):
        with self.assertRaises(ValueError):
            hit({"hits": 5})
        with self.assertRaises(UnknownCondition):
            hit({"hits": 0}, source_xy=(0,))


if __name__ == "__main__":
    unittest.main()
