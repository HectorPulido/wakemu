"""A finite free-cell search must retain native aligned targets."""
from types import SimpleNamespace as N
import unittest
from monster_pending_scenarios import bounded_empty_targets


class MonsterEmptyAlignmentTests(unittest.TestCase):
    def test_linear_candidates_precede_nearer_off_axis_cells(self):
        fight = N(
            actors={
                -200: N(position=(0, 0, 0), team=1, hp=100),
                7: N(position=(2, 2, 0), team=0, hp=100),
            },
            walkable={(2, 1, 0), (1, 2, 0), (2, 0, 0), (0, 2, 0)},
        )
        targets = bounded_empty_targets(
            fight, (0, 0, 0), 2, 4, prefer_linear=True, limit=2
        )
        self.assertEqual(set(targets), {(2, 0, 0), (0, 2, 0)})

    def test_diagonal_candidates_precede_nearer_non_diagonal_cells(self):
        fight = N(
            actors={-200: N(position=(0, 0, 0), team=1, hp=100)},
            walkable={(1, 0, 0), (0, 1, 0), (2, 2, 0)},
        )
        self.assertEqual(
            bounded_empty_targets(
                fight, (0, 0, 0), 1, 4, prefer_diagonal=True, limit=1
            ),
            [(2, 2, 0)],
        )
