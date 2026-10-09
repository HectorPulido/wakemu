"""Original426 missing internal spell dependencies extend the shared runtime source."""
import unittest
from wakfu_server.combat_triggered_dependencies import effect_catalog, merge_effects


class TriggeredClassDependencyTests(unittest.TestCase):
    def test_exact_native_scope_and_all_ordered_children_are_present(self):
        source = effect_catalog()
        self.assertEqual(
            set(source["spell_reference_closure"]), {7697, 7698, 7699, 8509, 6849}
        )
        self.assertEqual(len(source["effects"]), 314)
        self.assertEqual(len(source["added_effect_ids"]), 200)
        effects = source["effects"]
        for effect in effects.values():
            self.assertTrue(set(map(str, effect["children"])) <= set(effects))
            self.assertIs(type(effect["native_active_effect"]), bool)

    def test_existing_source_identity_preserved_missing_metadata_attested(self):
        source = effect_catalog()
        reference = next(iter(source["effects"]))
        effect = source["effects"][reference]
        previous = dict(effect)
        previous.pop("native_active_effect")
        merged = merge_effects({reference: previous})
        self.assertEqual(merged[reference], effect)
        self.assertNotIn("native_active_effect", previous)
        with self.assertRaises(ValueError):
            merge_effects({reference: {**effect, "parameters": [99999, 0]}})
