import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from export_monster_cell_groups import assert_preserved, export


class MonsterCellGroupImportTests(unittest.TestCase):
    def document(self, effects=None):
        return {
            "schema": "native-eYk-class-cell-group-v1",
            "source_hashes": {"class-export": "abc123"},
            "effects": effects
            or {
                "10": {
                    "criterion_present": True,
                    "area_class": "line",
                    "raw_parameters": [1, 2],
                }
            },
        }

    def test_append_only_guard_preserves_class_rows_hashes_and_export_prefix(self):
        base = self.document()
        old_export = {
            "original_inputs_stable": True,
            "effect_ids": [7],
            "original_input_hashes": {"a": "b"},
        }
        base["npc_dependency_exports"] = [old_export]
        candidate = copy.deepcopy(base)
        candidate["effects"]["20"] = {
            "criterion_present": False,
            "area_class": "circle",
            "raw_parameters": [3],
        }
        candidate["npc_dependency_exports"].append(
            {
                "original_inputs_stable": True,
                "effect_ids": [20],
                "original_input_hashes": {"client.jar": "sealed"},
                "original_export_sha256": "digest",
            }
        )

        assert_preserved(base, candidate)

        changed_class = copy.deepcopy(candidate)
        changed_class["effects"]["10"]["raw_parameters"] = [99]
        with self.assertRaisesRegex(ValueError, "changed original class"):
            assert_preserved(base, changed_class)

        changed_hashes = copy.deepcopy(candidate)
        changed_hashes["source_hashes"]["class-export"] = "different"
        with self.assertRaisesRegex(ValueError, "changed original class"):
            assert_preserved(base, changed_hashes)

        changed_prefix = copy.deepcopy(candidate)
        changed_prefix["npc_dependency_exports"][0]["effect_ids"] = [999]
        with self.assertRaisesRegex(ValueError, "changed original class"):
            assert_preserved(base, changed_prefix)

        unsealed = copy.deepcopy(candidate)
        unsealed["npc_dependency_exports"][1]["original_inputs_stable"] = False
        with self.assertRaisesRegex(ValueError, "provenance"):
            assert_preserved(base, unsealed)

        incomplete_ids = copy.deepcopy(candidate)
        incomplete_ids["npc_dependency_exports"][1]["effect_ids"] = [21]
        with self.assertRaisesRegex(ValueError, "dependency domain"):
            assert_preserved(base, incomplete_ids)

    def test_invalid_schema_and_parameter_types_are_rejected(self):
        invalid_schema = self.document()
        invalid_schema["schema"] = "unexpected"
        with self.assertRaisesRegex(ValueError, "schema"):
            assert_preserved(self.document(), invalid_schema)

        invalid_parameter = self.document()
        invalid_parameter["effects"]["10"]["raw_parameters"] = [True]
        with self.assertRaisesRegex(ValueError, "definition"):
            assert_preserved(self.document(), invalid_parameter)

        invalid_id = self.document()
        invalid_id["effects"]["010"] = invalid_id["effects"].pop("10")
        with self.assertRaisesRegex(ValueError, "definition"):
            assert_preserved(self.document(), invalid_id)

    def test_noop_export_skips_java_when_all_ids_are_known(self):
        base = self.document()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output = root / ".runtime" / "cell-group-export"
            with patch("export_monster_cell_groups.ROOT", root), patch(
                "export_monster_cell_groups.subprocess.run"
            ) as run:
                result = export(base, [10], root / "absent-bundle", output)

        self.assertIsNone(result)
        self.assertFalse(output.exists())
        run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
