import unittest

from wakfu_server.rii_lesson_spell_catalog import SPELL_ROOTS, GRANT_EFFECT, select
from wakfu_server.combat_effect_runtime import _merge_effects


class RiiLessonCatalogTests(unittest.TestCase):
    def fixture(self):
        roots = {ref for pair in SPELL_ROOTS.values() for ref in pair}
        effects = {str(ref): {"effect_class": 2, "children": []} for ref in roots}
        effects[str(GRANT_EFFECT)] = {"effect_class": 649, "children": []}
        return {
            "spells": {
                str(spell): {"level_zero_roots": list(pair)}
                for spell, pair in SPELL_ROOTS.items()
            },
            "effects": effects,
        }

    def test_only_training_closure_is_added_without_authorization(self):
        source = self.fixture()
        source["effects"]["999999"] = {"effect_class": 2, "children": []}
        selected = select(source)
        self.assertEqual(
            set(selected["effects"]),
            {str(ref) for pair in SPELL_ROOTS.values() for ref in pair}
            | {str(GRANT_EFFECT)},
        )
        existing = {"123": {"effect_class": 1, "children": []}}
        merged = _merge_effects(existing, selected)
        self.assertEqual(merged["123"], existing["123"])
        self.assertNotIn("999999", merged)

    def test_missing_or_changed_native_root_rejected(self):
        source = self.fixture()
        del source["effects"]["361189"]
        with self.assertRaises(ValueError):
            select(source)
        source = self.fixture()
        source["spells"]["7963"]["level_zero_roots"] = [361190]
        with self.assertRaises(ValueError):
            select(source)


if __name__ == "__main__":
    unittest.main()
