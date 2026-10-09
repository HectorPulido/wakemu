"""Source-proven PA-null differs from a null PV and unknown PA presence."""
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from wakfu_server.combat_hp_level_group import _value_group_override
from wakfu_server.combat_group_pv import group_pa


class GroupPANullTests(unittest.TestCase):
    def test_null_pa_skips_percentage_division_and_applies_base(self):
        effect = {
            "effect_class": 913,
            "parameters": sum(([v, 0] for v in (0, 0, 0, 0, 0, 0, 1, 1, 7, 2, 2)), []),
        }
        self.assertEqual(
            _value_group_override(
                effect,
                30,
                current=0,
                maximum=0,
                pa_absent=True,
                return_native_override=True,
            ),
            7,
        )
        with self.assertRaisesRegex(ValueError, "divides by zero"):
            _value_group_override(effect, 30, current=0, maximum=0)

    def test_verified_fav_null_and_unknown_override_are_distinct(self):
        fight = SimpleNamespace(
            native_effect_areas={91: {"native_area_contract": "faY"}}
        )
        with patch(
            "wakfu_server.combat_group_pv.resolve_group_level_pv",
            return_value=SimpleNamespace(native_is_area=True),
        ):
            self.assertIsNone(group_pa(fight, 91, 1))
            fight.native_effect_areas[91]["native_area_contract"] = "fbd"
            with self.assertRaisesRegex(ValueError, "presence authority"):
                group_pa(fight, 91, 1)

    def test_incomplete_actor_snapshot_is_not_null_pa(self):
        with patch(
            "wakfu_server.combat_group_pv.resolve_group_level_pv",
            return_value=SimpleNamespace(effect_stats={}, effect_maxima={}),
        ):
            with self.assertRaisesRegex(ValueError, "complete native PA"):
                group_pa(SimpleNamespace(), 7, 1)
