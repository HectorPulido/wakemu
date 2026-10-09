"""Scoped original class-profile source closure and zero-level contracts."""
import unittest
from wakfu_server.combat_morph_dependencies import (
    effect_catalog,
    zero_catalog,
    merge_effects,
)
from wakfu_server.combat_morph_spellbook import native_morph_profiles, build_morph_book


class MorphClassDependencyTests(unittest.TestCase):
    def test_actual_profile_book_and_complete_native_closure(self):
        profile = native_morph_profiles()["5900"]
        self.assertEqual(
            [row["reference"] for row in profile["abilities"]], [8588, 8589, 8590]
        )
        source = effect_catalog()
        self.assertEqual(len(source["effects"]), 141)
        self.assertEqual(len(source["added_effect_ids"]), 60)
        self.assertEqual(len(source["state_reference_closure"]), 15)
        self.assertTrue(source["original_zero_casting_verified"])
        for effect in source["effects"].values():
            self.assertIs(type(effect["native_active_effect"]), bool)
            self.assertTrue(
                all(str(child) in source["effects"] for child in effect["children"])
            )
        zero = zero_catalog()
        self.assertEqual(set(zero["spells"]), {"8588", "8589", "8590"})
        self.assertEqual(len(zero["effects"]), 60)
        for row in zero["spells"].values():
            self.assertTrue(
                all(str(reference) in zero["effects"] for reference in row[2])
            )
        for level in (0, 1, 153, 245):
            self.assertEqual(
                build_morph_book(profile, level),
                {8588: level, 8589: level, 8590: level},
            )

    def test_merge_preserves_existing_identity_and_rejects_native_flag_conflict(self):
        key, definition = next(iter(effect_catalog()["effects"].items()))
        existing = {key: dict(definition)}
        original = existing[key]
        self.assertIs(merge_effects(existing)[key], original)
        altered = dict(
            definition, native_active_effect=not definition["native_active_effect"]
        )
        with self.assertRaises(ValueError):
            merge_effects({key: altered})


if __name__ == "__main__":
    unittest.main()
