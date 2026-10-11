"""Bounded native validation search respects the actual scene."""
import sys
from pathlib import Path
from types import SimpleNamespace
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from monster_pending_scenarios import bounded_empty_targets


class MonsterEmptyTargetSearchTests(unittest.TestCase):
    def fight(self):
        actors = {
            -200: SimpleNamespace(position=(0, 0, 0), team=1, hp=100),
            7: SimpleNamespace(position=(2, 0, 0), team=0, hp=100),
            -201: SimpleNamespace(position=(0, 1, 0), team=1, hp=100),
        }
        return SimpleNamespace(
            actors=actors,
            native_obstacle_cells={(1, 1, 0)},
            walkable={(x, y, 0) for x in range(-3, 4) for y in range(-3, 4)},
        )

    def test_area_search_prioritizes_empty_cells_near_actual_hostile(self):
        cells = bounded_empty_targets(self.fight(), (0, 0, 0), 1, 1)
        self.assertEqual(cells[0], (1, 0, 0))

    def test_excludes_allies_companions_hostiles_and_native_obstacles(self):
        fight = self.fight()
        cells = bounded_empty_targets(fight, (0, 0, 0), 0, 3, limit=256)
        self.assertTrue(
            set(cells).isdisjoint(
                {actor.position for actor in fight.actors.values()}
                | fight.native_obstacle_cells
            )
        )

    def test_preserves_inclusive_native_range_and_deterministic_bound(self):
        fight = self.fight()
        cells = bounded_empty_targets(fight, (0, 0, 0), 2, 3, limit=4)
        self.assertEqual(len(cells), 4)
        self.assertTrue(all(2 <= abs(x) + abs(y) <= 3 for x, y, _ in cells))
        fight.walkable = list(reversed(sorted(fight.walkable)))
        self.assertEqual(cells, bounded_empty_targets(fight, (0, 0, 0), 2, 3, limit=4))

    def test_invalid_search_limits_are_rejected(self):
        for minimum, maximum, limit in (
            (-1, 2, 2),
            (3, 2, 2),
            (0, 2, 0),
            (0, 2, 257),
            (0, 2, True),
        ):
            with self.assertRaises(ValueError):
                bounded_empty_targets(
                    self.fight(), (0, 0, 0), minimum, maximum, limit=limit
                )
