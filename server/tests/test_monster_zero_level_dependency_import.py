"""Missing zero-only state effects are append-only original definitions."""
from copy import deepcopy
import unittest

from prepare_monster_spell_activation import supplement_zero_level_dependencies


class ZeroLevelDependencyImportTests(unittest.TestCase):
    def setUp(self):
        self.row = dict(
            minimum_level=0,
            maximum_level=0,
            effect_class=447,
            parameters=[5.0, 0.0],
            parameter_count=1,
            children=[],
            native_timing_definition=dict(ryE=1, ryF=0),
            native_target_selector=dict(mask=2, **{"class": "fcE"}),
            native_execution_mode=2,
            native_definition_class="eVy",
            parameters_by_level=[[5], [5]],
            probabilities=[100, 100],
        )
        self.exported = dict(
            spells={"1": {"levels": []}}, effects={"2": {"effect_class": 31}}
        )

    def supplement(self, required=("38688",), shared=()):
        return supplement_zero_level_dependencies(
            self.exported,
            required,
            shared,
            {"38688": self.row},
        )

    def test_import_preserves_every_original_field_and_zero_bounds(self):
        original = deepcopy(self.exported)
        result = self.supplement()
        self.assertEqual(result["effects"]["38688"], self.row)
        self.assertEqual(result["effects"]["2"], original["effects"]["2"])
        self.assertEqual(self.exported, original)
        result["effects"]["38688"]["parameters"][0] = 99
        self.assertEqual(self.row["parameters"][0], 5)

    def test_unneeded_and_shared_definitions_are_not_imported(self):
        self.assertNotIn("38688", self.supplement(required=())["effects"])
        self.assertNotIn("38688", self.supplement(shared=("38688",))["effects"])

    def test_existing_exported_definition_is_never_overridden(self):
        self.exported["effects"]["38688"] = dict(effect_class=447, sentinel="existing")
        self.assertEqual(
            self.supplement()["effects"]["38688"], self.exported["effects"]["38688"]
        )

    def test_positive_level_rows_do_not_silently_expand_import_scope(self):
        self.row["maximum_level"] = 200
        self.assertNotIn("38688", self.supplement()["effects"])

    def test_missing_full_native_metadata_fails_closed(self):
        for field in (
            "native_target_selector",
            "native_execution_mode",
            "native_timing_definition",
        ):
            with self.subTest(field=field):
                row = dict(self.row)
                row.pop(field)
                with self.assertRaisesRegex(ValueError, "Incomplete original"):
                    supplement_zero_level_dependencies(
                        self.exported, ["38688"], [], {"38688": row}
                    )


if __name__ == "__main__":
    unittest.main()
