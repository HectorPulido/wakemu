"""Area lesson uses one server-qualified multi-target cast per increment."""
import unittest
from types import SimpleNamespace

from wakfu_server.achievements.lesson_area import formation, observe
from wakfu_server.combat_effect_targets import area_offsets, select_effect_targets


class LessonAreaTests(unittest.TestCase):
    def event(self, state, **overrides):
        args = dict(
            owner_id=1,
            source_id=1,
            target_ids=(-1, -2, -3, -4),
            hit_ids=(-4, -3, -2, -1),
            effect_reference=367103,
            action_id=1,
        )
        args.update(overrides)
        return observe(state, **args)

    def test_four_distinct_complete_casts_and_replay(self):
        state = {"hits": 0, "actions": []}
        for action in range(1, 5):
            state = self.event(state, action_id=action)
            self.assertEqual(state["hits"], action)
            self.assertEqual(self.event(state, action_id=action), state)
        self.assertEqual(self.event(state, action_id=5), state)

    def test_partial_mismatched_wrong_owner_and_wrong_spell_do_not_count(self):
        initial = {"hits": 0, "actions": []}
        for args in (
            {"hit_ids": (-1, -2)},
            {"hit_ids": (-1, -2, -3, -3)},
            {"hit_ids": (-1, -2, -3, -5)},
            {"source_id": 2},
            {"effect_reference": 361204},
        ):
            self.assertEqual(self.event(initial, **args), initial)

    def test_invalid_target_and_corrupt_progress_fail_closed(self):
        with self.assertRaises(ValueError):
            self.event({"hits": 0, "actions": []}, target_ids=(-1, -1, -2, -3))
        with self.assertRaises(ValueError):
            self.event({"hits": 2, "actions": [1]})

    def test_candidate_layouts_use_real_native_area_shapes_and_avoid_occupied(self):
        effects = {
            "367103": {"area_class": "anG", "area_native": "rectangle or square-3x3"},
            "367142": {"area_class": "anw", "area_native": "cross-h2b2-g2d2"},
            "367145": {"area_class": "anH", "area_native": "ring-3-3"},
        }
        cells = {(x, y, 0) for x in range(-8, 9) for y in range(-8, 9)}
        occupied = {(1, 0, 0)}
        for phase, effect_id in enumerate(("367103", "367142", "367145")):
            center, positions = formation(
                cells, occupied, anchor=(0, 0, 0), phase=phase, effects=effects
            )
            self.assertGreaterEqual(abs(center[0]) + abs(center[1]), 2)
            self.assertEqual(len(set(positions)), 4)
            self.assertFalse(set(positions) & occupied)
            offsets = area_offsets(effects[effect_id])
            self.assertTrue(
                all((x - center[0], y - center[1]) in offsets for x, y, _ in positions)
            )
            caster = SimpleNamespace(id=1, team=0, position=(0, 0, 0))
            sacks = [
                SimpleNamespace(id=-(index + 1), team=1, position=point, hp=100)
                for index, point in enumerate(positions)
            ]
            selected = select_effect_targets(
                effects[effect_id], caster, center, sacks, relations={"enemy"}
            )
            self.assertEqual({actor.id for actor in selected}, {-1, -2, -3, -4})
        self.assertIsNone(
            formation({(0, 0, 0)}, (), anchor=(0, 0, 0), phase=0, effects=effects)
        )
        other_floor = {(x, y, 0) for x in range(-8, 9) for y in range(-8, 9)}
        self.assertIsNone(
            formation(other_floor, (), anchor=(0, 0, 3), phase=2, effects=effects)
        )
        center, positions = formation(
            other_floor,
            (),
            anchor=(0, 0, 3),
            phase=2,
            effects=effects,
            same_height=False,
        )
        self.assertEqual(center[2], 0)
        self.assertTrue(all(cell[2] == 0 for cell in positions))


if __name__ == "__main__":
    unittest.main()
