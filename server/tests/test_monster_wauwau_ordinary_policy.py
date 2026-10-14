"""Explicit implemented class producer policy; native summon routes stay open."""
import unittest
from wakfu_server.maps.monster_minigame_policy import (
    CLASS_SUMMON_BLOCKED_REFERENCES,
    exclusion_reason,
    require_ordinary_spawn,
)


class WauwauOrdinaryPolicyTests(unittest.TestCase):
    def test_implemented_class_4559_blocks_only_ordinary_wild_and_preserves_3251(self):
        self.assertEqual(CLASS_SUMMON_BLOCKED_REFERENCES, {3251, 4559})
        for reference in (4559, 3251):
            self.assertEqual(exclusion_reason(reference), "class_summon_implemented")
            with self.assertRaises(ValueError):
                require_ordinary_spawn(reference)
            self.assertIsNone(exclusion_reason(reference, context="native_summon"))
        self.assertIsNone(exclusion_reason(4558))
        require_ordinary_spawn(4558)
