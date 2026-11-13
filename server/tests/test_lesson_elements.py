import unittest

from wakfu_server.achievements.lesson_elements import observe, resistance_profile


class ElementalLessonTests(unittest.TestCase):
    def hit(self, state, **changes):
        event = dict(
            owner_id=1,
            target_id=-2,
            source_id=1,
            hit_target_id=-2,
            element=2,
            resistances={28: 0, 29: 50, 30: 50, 31: 50},
            turn_serial=1,
            damage=10,
        )
        event.update(changes)
        return observe(state, **event)

    def test_weakness_hits_can_repeat_in_the_same_turn(self):
        state = {"hits": 0, "last_turn": None}
        state = self.hit(state)
        self.assertEqual(state["hits"], 1)
        state = self.hit(state)
        self.assertEqual(state["hits"], 2)
        self.assertEqual(self.hit(state, turn_serial=2, element=3)["hits"], 2)
        state = self.hit(
            state, turn_serial=2, element=4, resistances={28: 50, 29: 0, 30: 50, 31: 50}
        )
        self.assertEqual(self.hit(state, turn_serial=1)["hits"], 3)
        state = self.hit(state, turn_serial=3)
        self.assertEqual(state, {"hits": 4, "last_turn": 3})
        self.assertEqual(self.hit(state, turn_serial=5), state)

    def test_wrong_actor_target_or_no_damage_does_not_count(self):
        state = {"hits": 0, "last_turn": None}
        for changes in (
            {"source_id": 3},
            {"hit_target_id": -3},
            {"damage": 0},
            {"element": 6},
        ):
            self.assertEqual(self.hit(state, **changes), state)

    def test_missing_authoritative_resistances_rejected(self):
        with self.assertRaises(ValueError):
            self.hit({"hits": 0, "last_turn": None}, resistances={28: 0})

    def test_profile_exposes_only_the_selected_weakness(self):
        self.assertEqual(
            resistance_profile(3), {28: 32000, 29: 32000, 30: 0, 31: 32000}
        )
        with self.assertRaises(ValueError):
            resistance_profile(1)


if __name__ == "__main__":
    unittest.main()
