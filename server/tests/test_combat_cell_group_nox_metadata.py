"""Additive Nox eYk metadata remains exact and guarded by class 349."""

import json
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from wakfu_server.combat_cell_group import native_cell_criterion_presence


METADATA_PATH = (
    Path(__file__).resolve().parents[2]
    / ".runtime/monster-deep-tests-20261014/nox-cell-group-export/native-class-cell-group-metadata.json"
)
NEW_REFERENCES = (392573, 392985, 392987, 392989)
BASELINE_PATH = (
    Path(__file__).resolve().parents[2]
    / ".runtime/monster-remote-20261014/local-docs/native-class-cell-group-metadata.json"
)


class NoxCellGroupMetadataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.artifact = json.loads(METADATA_PATH.read_text())
        cls.effects = cls.artifact["effects"]

    def test_all_four_native_exports_accept_exact_compiled_rows(self):
        with patch(
            "wakfu_server.combat_cell_group.native_cell_group_metadata",
            return_value=self.effects,
        ):
            for reference in NEW_REFERENCES:
                with self.subTest(reference=reference):
                    row = self.effects[str(reference)]
                    effect = {
                        "effect_class": 349,
                        "area_class": row["area_class"],
                        "parameters": list(row["raw_parameters"]),
                    }
                    self.assertTrue(
                        native_cell_criterion_presence(
                            effect, SimpleNamespace(reference=reference)
                        )
                    )

    def test_missing_or_mismatching_native_metadata_still_rejects(self):
        reference = NEW_REFERENCES[0]
        source = self.effects[str(reference)]
        effect = {
            "effect_class": 349,
            "area_class": source["area_class"],
            "parameters": list(source["raw_parameters"]),
        }
        with patch(
            "wakfu_server.combat_cell_group.native_cell_group_metadata", return_value={}
        ):
            with self.assertRaisesRegex(ValueError, "matching native eYk"):
                native_cell_criterion_presence(
                    effect, SimpleNamespace(reference=reference)
                )

        with patch(
            "wakfu_server.combat_cell_group.native_cell_group_metadata",
            return_value=self.effects,
        ):
            for changed in (
                dict(effect, area_class="anA"),
                dict(effect, parameters=[2.0, *effect["parameters"][1:]]),
            ):
                with self.subTest(changed=changed):
                    with self.assertRaisesRegex(ValueError, "matching native eYk"):
                        native_cell_criterion_presence(
                            changed, SimpleNamespace(reference=reference)
                        )

    def test_candidate_only_adds_four_rows_and_preserves_every_previous_row(self):
        baseline = json.loads(BASELINE_PATH.read_text())
        old, new = baseline["effects"], self.artifact["effects"]
        self.assertEqual(baseline["schema"], self.artifact["schema"])
        self.assertEqual(baseline["source_sha256"], self.artifact["source_sha256"])
        self.assertEqual(set(new) - set(old), {str(value) for value in NEW_REFERENCES})
        self.assertEqual(set(old) - set(new), set())
        for reference, row in old.items():
            with self.subTest(reference=reference):
                self.assertEqual(new[reference], row)


if __name__ == "__main__":
    unittest.main()
