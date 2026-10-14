"""Preserve native target identity after genuine preparation movement."""
from pathlib import Path
import sys
import unittest
from types import SimpleNamespace as NS

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from monster_pending_scenarios import refresh_native_actor_targets


class ActualTargetCellTests(unittest.TestCase):
    def test_native_producer_pull_refreshes_same_consumer_actor_without_retargeting(
        self,
    ):
        fight = NS(
            actors={
                -200: NS(position=(-6, -8, -1), hp=2000),
                -201: NS(position=(-7, -7, -1), hp=300),
                7: NS(position=(-9, -8, -1), hp=60),
            }
        )
        before = [
            ((-10, -7, -1), -201),
            ((-8, -7, -1), -200),
            ((-9, -8, -1), 7),
            ((-10, -7, -1), None),
        ]
        after = refresh_native_actor_targets(fight, before)
        self.assertEqual(
            [identity for _, identity in after], [identity for _, identity in before]
        )
        self.assertEqual(after[0], ((-7, -7, -1), -201))
        self.assertEqual(after[1], ((-6, -8, -1), -200))
        self.assertEqual(after[2:], before[2:])
        self.assertEqual(before[0], ((-10, -7, -1), -201))
        fight.actors[-201].hp = 0
        self.assertEqual(refresh_native_actor_targets(fight, before)[0], before[0])


if __name__ == "__main__":
    unittest.main()
