import unittest

from wakfu_server.achievements.lesson_states import observe


class StateLessonTests(unittest.TestCase):
    def step(self, hits, **changes):
        arguments = dict(
            owner_id=7,
            target_id=-3,
            actor_id=7,
            target_actor_id=-3,
            event="turn_end",
            actor_xy=(6, 0),
            target_xy=(0, 0),
            green=(2, 0),
            red=(3, 0),
            spell_id=None,
        )
        arguments.update(changes)
        return observe({"hits": hits}, **arguments)

    def test_four_native_conditions_and_boundaries(self):
        self.assertEqual(self.step(0, actor_xy=(5, 0)), {"hits": 0})
        self.assertEqual(
            self.step(0, event="hit", actor_xy=(2, 0), spell_id=7967), {"hits": 1}
        )
        self.assertEqual(
            self.step(1, event="hit", actor_xy=(3, 0), spell_id=7967), {"hits": 2}
        )
        self.assertEqual(self.step(2, actor_xy=(2, 0)), {"hits": 2})
        self.assertEqual(self.step(2, actor_xy=(1, 0)), {"hits": 3})
        self.assertEqual(self.step(3, actor_xy=(6, 0)), {"hits": 4})
        self.assertEqual(self.step(4), {"hits": 4})

    def test_wrong_identity_event_spell_and_cell_do_not_progress(self):
        self.assertEqual(self.step(0, actor_id=8), {"hits": 0})
        self.assertEqual(self.step(0, target_actor_id=-4), {"hits": 0})
        self.assertEqual(
            self.step(1, event="hit", actor_xy=(1, 0), spell_id=7967), {"hits": 1}
        )
        self.assertEqual(
            self.step(0, event="hit", actor_xy=(2, 0), spell_id=7968), {"hits": 0}
        )
        self.assertEqual(
            self.step(1, event="hit", actor_xy=(2, 0), spell_id=7967), {"hits": 1}
        )

    def test_bad_contract_rejected_and_source_not_mutated(self):
        original = {"hits": 0}
        observe(
            original,
            owner_id=7,
            target_id=-3,
            actor_id=7,
            target_actor_id=-3,
            event="turn_end",
            actor_xy=(6, 0),
            target_xy=(0, 0),
            green=(2, 0),
            red=(3, 0),
        )
        self.assertEqual(original, {"hits": 0})
        with self.assertRaises(ValueError):
            self.step(0, green=(2, 0), red=(2, 0))


if __name__ == "__main__":
    unittest.main()
