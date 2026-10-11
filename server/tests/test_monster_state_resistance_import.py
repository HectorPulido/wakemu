import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from export_monster_state_resistance import assert_preserved, export, merge


class MonsterStateResistanceImportTests(unittest.TestCase):
    def document(self, state_ids, states, missing, provenance=True):
        return {
            "schema": "native-class-state-resistance-v1",
            "seed_identity": {
                "schema": "native-class-state-resistance-seeds-v1",
                "state_ids": state_ids,
                "class_seed_note": {"owner": "class-export"},
            },
            "provenance": {"original_inputs_stable": provenance, "class": "sealed"},
            "enum_ordinals": {"NEGATIF": 0, "NEUTRAL": 1, "POSITIF": 2},
            "native_level_checks": 6 * len(states),
            "missing_state_ids": missing,
            "states": states,
            "class_metadata": {"preserve": ["exactly", "as-is"]},
        }

    @staticmethod
    def state(name="POSITIF", ordinal=2):
        return {
            "native_getter": "fyW.elk",
            "native_resistance_mode": {
                "enum_class": "fza",
                "name": name,
                "ordinal": ordinal,
            },
        }

    def test_merge_appends_sealed_addition_and_preserves_existing_class_data(self):
        base = self.document([100, 200], {"100": self.state()}, [200])
        addition = self.document([300], {"300": self.state("NEUTRAL", 1)}, [])
        base_before = copy.deepcopy(base)

        result = merge(base, addition)

        self.assertEqual(result["states"]["100"], base["states"]["100"])
        self.assertEqual(result["states"]["300"], addition["states"]["300"])
        self.assertEqual(result["missing_state_ids"], [200])
        self.assertEqual(result["seed_identity"]["state_ids"], [100, 200, 300])
        self.assertEqual(result["native_level_checks"], 12)
        self.assertEqual(result["class_metadata"], base_before["class_metadata"])
        self.assertEqual(
            result["seed_identity"]["class_seed_note"],
            base_before["seed_identity"]["class_seed_note"],
        )
        self.assertEqual(result["provenance"], base_before["provenance"])
        self.assertEqual(base, base_before)
        self.assertEqual(len(result["npc_dependency_exports"]), 1)
        assert_preserved(base, result)

    def test_merge_rejects_enum_conflicts_and_changed_values_or_attested_absence(self):
        base = self.document([100], {"100": self.state()}, [])

        conflicting_enum = self.document([200], {"200": self.state("NEUTRAL", 1)}, [])
        conflicting_enum["enum_ordinals"]["NEUTRAL"] = 0
        with self.assertRaisesRegex(ValueError, "domain"):
            merge(base, conflicting_enum)

        changed_value = self.document([100], {"100": self.state("NEUTRAL", 1)}, [])
        with self.assertRaisesRegex(ValueError, "definition"):
            merge(base, changed_value)

        newly_absent = self.document([100], {}, [100])
        with self.assertRaisesRegex(ValueError, "became absent"):
            merge(base, newly_absent)

        replaces_attested_absence = self.document(
            [100, 200], {"100": self.state(), "200": self.state()}, []
        )
        base_with_absence = self.document([100, 200], {"100": self.state()}, [200])
        with self.assertRaisesRegex(ValueError, "absence changed"):
            merge(base_with_absence, replaces_attested_absence)

    def test_merge_rejects_unsealed_documents_and_invalid_state_domains(self):
        base = self.document([100], {"100": self.state()}, [])
        unsealed = self.document([200], {"200": self.state()}, [], provenance=False)
        with self.assertRaisesRegex(ValueError, "Unsealed"):
            merge(base, unsealed)

        invalid = self.document([200], {"200": self.state()}, [])
        invalid["native_level_checks"] = 5
        with self.assertRaisesRegex(ValueError, "domain"):
            merge(base, invalid)

    def test_publication_guard_preserves_all_old_rows_provenance_and_seed_extras(self):
        base = self.document([100], {"100": self.state()}, [])
        addition = self.document([200], {"200": self.state("NEUTRAL", 1)}, [])
        candidate = merge(base, addition)

        changed_row = copy.deepcopy(candidate)
        changed_row["states"]["100"]["native_resistance_mode"]["name"] = "NEUTRAL"
        with self.assertRaisesRegex(ValueError, "Invalid original resistance enum"):
            assert_preserved(base, changed_row)

        changed_provenance = copy.deepcopy(candidate)
        changed_provenance["provenance"]["class"] = "changed"
        with self.assertRaisesRegex(ValueError, "changed existing"):
            assert_preserved(base, changed_provenance)

        changed_seed_extra = copy.deepcopy(candidate)
        changed_seed_extra["seed_identity"]["class_seed_note"]["owner"] = "npc"
        with self.assertRaisesRegex(ValueError, "changed existing"):
            assert_preserved(base, changed_seed_extra)

        unsealed_addition = copy.deepcopy(candidate)
        unsealed_addition["npc_dependency_exports"][0]["provenance"][
            "original_inputs_stable"
        ] = False
        with self.assertRaisesRegex(ValueError, "Missing sealed"):
            assert_preserved(base, unsealed_addition)

        no_addition = copy.deepcopy(base)
        with self.assertRaisesRegex(ValueError, "Missing sealed"):
            assert_preserved(base, no_addition)

    def test_export_is_noop_when_all_dependencies_are_already_covered(self):
        base = self.document([100], {"100": self.state()}, [])
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            bundle = root / "bundle"
            bundle.mkdir()
            output = root / ".runtime" / "resistance-export"
            with patch("export_monster_state_resistance.ROOT", root), patch(
                "export_monster_state_resistance.subprocess.run"
            ) as run:
                result = export(base, [100], bundle, output)

        self.assertIsNone(result)
        self.assertFalse(output.exists())
        run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
