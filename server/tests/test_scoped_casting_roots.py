import unittest
from wakfu_server.combat_scoped_casting_roots import merge_casting_roots
from wakfu_server import native_catalog


class ScopedCastingRootTests(unittest.TestCase):
    def test_captured_books_have_complete_real_critical_and_casting_root_domain(self):
        import json
        from wakfu_server.paths import DATA_ROOT
        from wakfu_server.combat_scoped_casting_roots import captured_casting_roots
        from wakfu_server.combat_casting_context import casting_root_catalog
        from wakfu_server.combat_critical import spell_critical_available

        profiles = json.loads(
            native_catalog.read_text(DATA_ROOT / "native-class-captured-profiles.json")
        )["profiles"]
        with native_catalog.open(
            DATA_ROOT / "native-spell-casting.json", "rt"
        ) as stream:
            casting = json.load(stream)["spells"]
        source, actual = captured_casting_roots(), casting_root_catalog()
        references = {
            row["reference"]
            for profile in profiles.values()
            for row in profile["abilities"]
        }
        self.assertEqual(set(source["spell_references"]), references)
        for profile in profiles.values():
            for action in profile["abilities"]:
                reference = action["reference"]
                for level in range(1, 201):
                    evaluated = min(
                        action["maximum_level"],
                        level
                        if action["override_level"] == -1
                        else action["override_level"],
                    )
                    self.assertIs(
                        type(spell_critical_available(reference, evaluated)), bool
                    )
                    roots = casting[str(reference)]["levels"][evaluated - 1][2]
                    for root in roots:
                        self.assertEqual(
                            actual["roots"][str(root)], source["roots"][str(root)]
                        )
        self.assertEqual(
            {row["reference"] for row in profiles["4"]["abilities"]},
            {549, 7359, 7360, 7361},
        )

    def test_original_morph_source_is_installed_in_actual_casting_catalog(self):
        from wakfu_server.combat_scoped_casting_roots import morph_casting_roots
        from wakfu_server.combat_casting_context import casting_root_catalog

        source = morph_casting_roots()
        actual = casting_root_catalog()
        self.assertEqual(len(source["roots"]), 12)
        for reference, record in source["roots"].items():
            self.assertEqual(actual["roots"][reference], record)
            self.assertIn("native_casting_collision_area", record)
            self.assertEqual(
                record["native_selector_present"],
                record["native_target_selector"] is not None,
            )

    def test_null_geometry_and_selector_are_preserved_without_defaults(self):
        original = {
            "native_casting_collision_area": None,
            "native_selector_present": False,
            "native_target_selector": None,
        }
        existing = {
            "fight_properties": {"sdG": 1},
            "normal_casting_overrides": {},
            "roots": {"1": original},
        }
        additional = {
            "fight_properties": {"sdG": 1},
            "normal_casting_overrides": {},
            "roots": {"2": dict(original)},
        }
        merged = merge_casting_roots(existing, additional)
        self.assertIs(merged["roots"]["1"], original)
        self.assertEqual(merged["roots"]["2"], original)
        self.assertEqual(set(existing["roots"]), {"1"})

    def test_conflicting_native_root_and_global_authority_rejected(self):
        existing = {
            "fight_properties": {},
            "normal_casting_overrides": {},
            "roots": {"1": {"native_selector_present": False}},
        }
        with self.assertRaises(ValueError):
            merge_casting_roots(
                existing,
                {**existing, "roots": {"1": {"native_selector_present": True}}},
            )
        with self.assertRaises(ValueError):
            merge_casting_roots(existing, {**existing, "fight_properties": {"sdG": 1}})
