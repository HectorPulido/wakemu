"""Qualification of reviewed quest interaction batch data."""
import copy
import json
from pathlib import Path
import unittest

from tools.install_quest_interactions import validate_manifest


class BatchManifestTests(unittest.TestCase):
    def setUp(self):
        self.revision = "a" * 64
        self.row = {
            "status": "reviewed",
            "map_id": 1,
            "object_id": 3,
            "action_id": 0,
            "parameter": 0,
            "x": 1,
            "y": -2,
            "z": 0,
            "object_type": "GenericActivableInteractiveElement",
            "max_distance": 4,
            "required_item": 42,
            "required_quantity": 1,
            "quest_id": 7,
            "objective_id": 8,
            "evidence": "native active condition and object",
        }
        self.document = {"schema": "quest-interaction-batch-v1", "bindings": [self.row]}

    def test_preserves_identity_and_revision(self):
        row = validate_manifest(self.document, self.revision)[0]
        self.assertEqual(
            (row["quest_id"], row["objective_id"], row["revision"]),
            (7, 8, self.revision),
        )
        self.assertEqual((row["required_item"], row["required_quantity"]), (42, 1))

    def test_rejects_ambiguous_unreviewed_or_malformed_bindings(self):
        for key, value in [
            ("status", "candidate"),
            ("evidence", ""),
            ("required_quantity", 0),
            ("action_id", -1),
            ("x", True),
            ("approach_cells", [999, 0, 0]),
            ("approach_cells", [1, 2]),
        ]:
            document = copy.deepcopy(self.document)
            document["bindings"][0][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                validate_manifest(document, self.revision)
        document = copy.deepcopy(self.document)
        document["bindings"].append(copy.deepcopy(document["bindings"][0]))
        with self.assertRaisesRegex(ValueError, "duplicate"):
            validate_manifest(document, self.revision)

    def test_native_position_trigger_accepts_only_its_pinned_walkon_polygon(self):
        from wakfu_server import native_interactive_activation, world_static

        source_profile = json.loads(
            (
                Path(__file__).parents[1]
                / "wakfu_server/achievements/quest_source_profiles/ereboria-camp-entry.json"
            ).read_text()
        )
        row = source_profile["bindings"][0]
        native = next(
            item for item in world_static.objects(1358) if item["id"] == 33687
        )
        positions = native_interactive_activation.decode(native)
        self.assertEqual(len(positions), 17)
        self.assertEqual(
            validate_manifest(source_profile, self.revision)[0]["approach_cells"],
            [coordinate for position in positions for coordinate in position],
        )

        altered = copy.deepcopy(source_profile)
        altered["bindings"][0]["approach_cells"][0] += 1
        with self.assertRaisesRegex(ValueError, "exact native activation polygon"):
            validate_manifest(altered, self.revision)

        altered = copy.deepcopy(source_profile)
        altered["bindings"][0]["native_activation_source_sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "does not match installed content"):
            validate_manifest(altered, self.revision)

        altered = copy.deepcopy(source_profile)
        altered["bindings"][0]["action_id"] = 0
        with self.assertRaisesRegex(ValueError, "exact WALKON action"):
            validate_manifest(altered, self.revision)

        legacy = copy.deepcopy(source_profile)
        legacy_row = legacy["bindings"][0]
        legacy_row.pop("native_activation_source_sha256")
        legacy_row["approach_cells"] = [
            coordinate
            for index in range(10)
            for coordinate in (
                legacy_row["x"] + index,
                legacy_row["y"],
                legacy_row["z"],
            )
        ]
        with self.assertRaisesRegex(ValueError, "approach cells"):
            validate_manifest(legacy, self.revision)


if __name__ == "__main__":
    unittest.main()
