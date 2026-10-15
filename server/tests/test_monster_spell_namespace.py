"""Regression coverage for overlapping native state and spell identifiers."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from monster_spell_namespace import validate_spell_namespace


class MonsterSpellNamespaceTests(unittest.TestCase):
    def test_accepts_spell_level_ranges_and_effect_roots(self):
        validate_spell_namespace({"8368": {"levels": [[0, 0, [392568]]]}})

    def test_rejects_colliding_state_definition(self):
        with self.assertRaisesRegex(ValueError, "8368"):
            validate_spell_namespace(
                {"8368": {"levels": [{"effects": [381722], "duration": -1}]}}
            )

    def test_rejects_invalid_root_type(self):
        with self.assertRaises(ValueError):
            validate_spell_namespace({"8368": {"levels": [[0, 0, [True]]]}})
