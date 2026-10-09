import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from morph_audit_serialization import normalize_morph_evidence


class MorphAuditSerializationTests(unittest.TestCase):
    def test_native_removed_uid_set_preserves_identity_and_unknown_and_geometry(self):
        value = {
            "temporary_book": {"removed_raw_uids": {8590, 8588}, "levels": {8588: 200}},
            "diagnostics": {"unknown": None, "cell": (-22, -142, 70)},
        }
        facts = []
        normalized = normalize_morph_evidence(value, set_projections=facts)
        self.assertEqual(normalized["temporary_book"]["removed_raw_uids"], [8588, 8590])
        self.assertIsNone(normalized["diagnostics"]["unknown"])
        self.assertEqual(normalized["diagnostics"]["cell"], [-22, -142, 70])
        self.assertEqual(facts[0]["path"], ["temporary_book", "removed_raw_uids"])
        self.assertEqual(value["temporary_book"]["removed_raw_uids"], {8590, 8588})
        json.dumps(normalized, allow_nan=False)

    def test_unclassified_set_and_actor_object_are_not_stringified(self):
        with self.assertRaisesRegex(ValueError, "Undeclared semantic set"):
            normalize_morph_evidence({"actor": {7}})
        with self.assertRaisesRegex(ValueError, "Unsupported audit evidence type"):
            normalize_morph_evidence({"actor": object()})
