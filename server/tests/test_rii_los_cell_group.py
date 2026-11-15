"""Native LOS cell selector must use the exact exported eYk definition."""

from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from wakfu_server.combat_cell_group import (
    native_cell_criterion_presence,
    rii_cell_group_metadata,
)


class RiiLosCellGroupTests(TestCase):
    def test_exact_native_selector_and_mismatches(self):
        effect = {
            "effect_class": 349,
            "area_class": "anu",
            "parameters": [1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0],
        }
        invocation = SimpleNamespace(reference=367418)
        with patch(
            "wakfu_server.combat_cell_group.native_cell_group_metadata", return_value={}
        ):
            self.assertTrue(native_cell_criterion_presence(effect, invocation))
            for changed in (
                dict(effect, effect_class=315),
                dict(effect, area_class="anA"),
                dict(effect, parameters=[2.0] + effect["parameters"][1:]),
            ):
                with self.assertRaises(ValueError):
                    native_cell_criterion_presence(changed, invocation)
            with self.assertRaises(ValueError):
                native_cell_criterion_presence(
                    effect, SimpleNamespace(reference=367419)
                )

    def test_reviewed_lesson_supplement_matches_all_native_parameters(self):
        metadata = rii_cell_group_metadata()
        self.assertEqual(
            set(metadata),
            {
                "367176",
                "367179",
                "367184",
                "367187",
                "367190",
                "367193",
                "367196",
                "367199",
                "367272",
                "367276",
                "367284",
                "367286",
                "367418",
                "409656",
                "409659",
            },
        )
        self.assertEqual(
            metadata["409656"],
            {
                "area_class": "anu",
                "criterion_present": True,
                "raw_parameters": [1.0, 0.0, 0.0, 0.0, 1.0, 0.0],
            },
        )
        self.assertEqual(metadata["409659"], metadata["409656"])
        with patch(
            "wakfu_server.combat_cell_group.native_cell_group_metadata", return_value={}
        ):
            for raw_reference, row in metadata.items():
                reference = int(raw_reference)
                effect = {
                    "effect_class": 349,
                    "area_class": row["area_class"],
                    "parameters": row["raw_parameters"],
                }
                with self.subTest(reference=reference):
                    self.assertEqual(
                        native_cell_criterion_presence(
                            effect, SimpleNamespace(reference=reference)
                        ),
                        row["criterion_present"],
                    )

            definition = metadata["367284"]
            effect = {
                "effect_class": 349,
                "area_class": definition["area_class"],
                "parameters": definition["raw_parameters"],
            }
            for changed in (
                dict(effect, area_class="anu"),
                dict(effect, parameters=[7.0, *effect["parameters"][1:]]),
                dict(effect, effect_class=315),
            ):
                with self.subTest(changed=changed):
                    with self.assertRaisesRegex(ValueError, "matching native eYk"):
                        native_cell_criterion_presence(
                            changed, SimpleNamespace(reference=367284)
                        )
