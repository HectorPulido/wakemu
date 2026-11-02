"""Companion breed recommendations do not clamp an authored actor level."""
from copy import deepcopy
import unittest
from unittest.mock import patch

from wakfu_server.combat_companions import COMPANION_BREEDS, native_stats


class CompanionRecommendedLevelTests(unittest.TestCase):
    def test_native_curve_receives_exact_level_outside_recommendation(self):
        breed = next(iter(COMPANION_BREEDS))
        values = {
            key: dict(current=amount, minimum=0, maximum=amount, frozen=False)
            for key, amount in ((1, 1234), (2, 6), (3, 3), (4, 6))
        }
        with patch(
            "wakfu_server.monsters.reference",
            return_value=dict(min_level=1, max_level=10),
        ), patch(
            "wakfu_server.combat_actor_snapshot.native_npc_creation_values",
            return_value=deepcopy(values),
        ) as creation, patch(
            "wakfu_server.combat_actor_snapshot.native_actor_catalog",
            return_value={
                "characteristics": {
                    str(key): {"hard_minimum": 0, "hard_maximum": 32767}
                    for key in (1, 2, 3, 4)
                }
            },
        ), patch(
            "wakfu_server.combat_companions.equipment_bonuses", return_value={}
        ), patch(
            "wakfu_server.monsters.statistics", return_value={"INIT": 91}
        ) as statistics:
            result = native_stats(breed, 215)
            creation.assert_called_once_with(breed, 215)
            statistics.assert_called_once_with(breed, 215)
            self.assertEqual((result["hp"], result["initiative"]), (1234, 91))
            for level in (0, -1, 32768, True, 215.0):
                with self.subTest(level=level), self.assertRaisesRegex(
                    ValueError, "Invalid companion level"
                ):
                    native_stats(breed, level)
