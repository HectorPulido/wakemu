"""Explicit implemented class policy preserves actual native summons."""
import unittest
from wakfu_server.maps import monster_minigame_policy as p


class ClassPolicyTests(unittest.TestCase):
    def test_original_baseline_and_native_context_preserved(self):
        self.assertEqual(p.CLASS_SUMMON_BLOCKED_REFERENCES, {3251, 4559})
        self.assertEqual(len(p.ADDITIONAL_IMPLEMENTED_CLASS_SUMMON_REFERENCES), 18)
        for ref in p.ADDITIONAL_IMPLEMENTED_CLASS_SUMMON_REFERENCES:
            self.assertEqual(p.exclusion_reason(ref), "class_summon_implemented")
            self.assertIsNone(p.exclusion_reason(ref, context="native_summon"))

    def test_positive_npc_routes_remain_in_dependency_domain(self):
        for ref in (3745, 3748, 3750):
            self.assertEqual(p.exclusion_reason(ref), "class_summon_implemented")
            self.assertTrue(p.requires_npc_summon_validation(ref))
            self.assertIsNone(p.exclusion_reason(ref, context="native_summon"))
        self.assertTrue(p.requires_npc_summon_validation(3251))
        self.assertIsNone(p.exclusion_reason(6))
