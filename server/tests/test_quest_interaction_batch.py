"""Qualification of reviewed quest interaction batch data."""
import copy
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
        ]:
            document = copy.deepcopy(self.document)
            document["bindings"][0][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                validate_manifest(document, self.revision)
        document = copy.deepcopy(self.document)
        document["bindings"].append(copy.deepcopy(document["bindings"][0]))
        with self.assertRaisesRegex(ValueError, "duplicate"):
            validate_manifest(document, self.revision)


if __name__ == "__main__":
    unittest.main()
