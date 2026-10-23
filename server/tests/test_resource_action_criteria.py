"""Pure resource criterion contracts; no catalog or database import."""
import unittest

from wakfu_server.resource_action_criteria import (
    allows,
    authorize,
    minimum_effective_level,
)


class ResourceActionCriteriaTests(unittest.TestCase):
    def test_native_level_fragment_rechecks_modulation_at_each_phase(self):
        # The four original 757/2118 rows share this fragment; no IDs are policy.
        rule = {"action_id": 2118, "criteria": "GetLevel() >= 10"}
        for scenario in (-1953, -1949, -1945, -1941):
            with self.subTest(scenario=scenario):
                self.assertIs(authorize(rule, effective_level=201), rule)
                self.assertIs(authorize(rule, effective_level=10), rule)
                # A real-level-245 actor modulated to nine must fail completion.
                with self.assertRaises(ValueError):
                    authorize(rule, effective_level=9)
        self.assertEqual(minimum_effective_level(" (GetLevel() >= 17) "), 17)
        self.assertFalse(allows("GetLevel() >= 17", effective_level=16))
        self.assertTrue(allows("GetLevel() >= 17", effective_level=17))
        self.assertTrue(allows("", effective_level=1))
        self.assertEqual(rule, {"action_id": 2118, "criteria": "GetLevel() >= 10"})

    def test_unsupported_syntax_and_non_authoritative_levels_fail_closed(self):
        for text in (
            "GetRealLevel() >= 10",
            "GetLevel(target) >= 10",
            "GetLevel(actor=1) >= 10",
            "GetLevel() > 10",
            "10 <= GetLevel()",
            "GetLevel() >= True",
            "GetLevel() >= 10.0",
            "GetLevel() >= -1",
            "GetLevel() >= 32768",
            "GetLevel() >= 10 or True",
            "0 <= GetLevel() >= 10",
            "actor.GetLevel() >= 10",
            "GetLevel()",
        ):
            with self.subTest(text=text), self.assertRaises(ValueError):
                allows(text, effective_level=245)
        for value in (None, True, 0, -1, 10.0, "245", 32768):
            with self.subTest(level=value), self.assertRaises(ValueError):
                allows("GetLevel() >= 10", effective_level=value)
        with self.assertRaises(ValueError):
            minimum_effective_level(None)
        with self.assertRaises(ValueError):
            minimum_effective_level("x" * 1025)
