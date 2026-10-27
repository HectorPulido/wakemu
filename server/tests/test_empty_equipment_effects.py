import hashlib
import json
import unittest
from pathlib import Path
from unittest.mock import patch

from wakfu_server import native_catalog
from wakfu_server.equipment import RULES, validate_sheet
from wakfu_server import empty_equipment_effects
from wakfu_server.wire import proto_field


class EmptyEquipmentEffectsTests(unittest.TestCase):
    def setUp(self):
        empty_equipment_effects.definitions.cache_clear()

    def tearDown(self):
        empty_equipment_effects.definitions.cache_clear()

    def test_626_templates_document_identity_release_independence_and_tamper(self):
        path = Path(empty_equipment_effects.__file__).with_name(
            "native_empty_equipment_effects.json"
        )
        raw = path.read_bytes()
        self.assertEqual(
            empty_equipment_effects.SOURCE_SHA256, hashlib.sha256(raw).hexdigest()
        )
        manifests = (
            Path(__file__).resolve().parents[1] / "data" / "installation" / "catalogs"
        )
        old = json.loads((manifests / "manifest.json").read_bytes())
        new = json.loads((manifests / "manifest-rift-cell-groups-v1.json").read_bytes())

        def hashes(manifest):
            release = next(
                row
                for row in manifest["releases"]
                if row["revision"] == manifest["active_revision"]
            )
            return {row["path"]: row["sha256"] for row in release["documents"]}

        old_hashes, new_hashes = hashes(old), hashes(new)
        self.assertNotEqual(old["active_revision"], new["active_revision"])
        self.assertEqual(
            {
                name
                for name in old_hashes.keys() | new_hashes.keys()
                if old_hashes.get(name) != new_hashes.get(name)
            },
            {"native-class-cell-group-metadata.json"},
        )
        for manifest, published in ((old, old_hashes), (new, new_hashes)):
            empty_equipment_effects.definitions.cache_clear()
            with patch.object(
                native_catalog, "release", return_value=manifest["active_revision"]
            ), patch.object(native_catalog, "document_hashes", return_value=published):
                self.assertEqual(len(empty_equipment_effects.definitions()), 626)
        empty_equipment_effects.definitions.cache_clear()

        rows = empty_equipment_effects.definitions()
        self.assertEqual(626, len(rows))
        for reference, row in rows.items():
            with self.subTest(reference=reference):
                self.assertEqual([], row["effects"])
                self.assertIsNotNone(RULES.get(reference))
                self.assertEqual(
                    {
                        key: RULES[reference][key]
                        for key in (
                            "minimum_level",
                            "native_dte",
                            "slots",
                            "occupied_slots",
                            "has_conditions",
                        )
                    },
                    {
                        key: row[key]
                        for key in (
                            "minimum_level",
                            "native_dte",
                            "slots",
                            "occupied_slots",
                            "has_conditions",
                        )
                    },
                )
                self.assertEqual(
                    [], empty_equipment_effects.template(reference)["effects"]
                )

        self.assertIsNone(empty_equipment_effects.template(999999999))
        self._assert_hash_and_rule_conflicts_fail_closed()

    def _assert_hash_and_rule_conflicts_fail_closed(self):
        empty_equipment_effects.definitions.cache_clear()
        original_read_bytes = Path.read_bytes
        target = Path(empty_equipment_effects.__file__).with_name(
            "native_empty_equipment_effects.json"
        )

        def altered_read_bytes(path):
            if path == target:
                return original_read_bytes(path) + b" "
            return original_read_bytes(path)

        with patch.object(Path, "read_bytes", altered_read_bytes):
            with self.assertRaisesRegex(
                ValueError, "Conflicting original empty equipment"
            ):
                empty_equipment_effects.definitions()
        empty_equipment_effects.definitions.cache_clear()

        for published in ({}, {empty_equipment_effects.RULES_DOCUMENT: "0" * 64}):
            with patch.object(
                native_catalog, "document_hashes", return_value=published
            ):
                with self.assertRaisesRegex(
                    ValueError, "conflict with published native rules"
                ):
                    empty_equipment_effects.definitions()
            empty_equipment_effects.definitions.cache_clear()

        reference = next(iter(empty_equipment_effects.definitions()))
        mismatched = dict(
            RULES[reference], minimum_level=RULES[reference]["minimum_level"] + 1
        )
        with patch.dict("wakfu_server.equipment.RULES", {reference: mismatched}):
            with self.assertRaisesRegex(ValueError, "conflicts with native rules"):
                empty_equipment_effects.template(reference)

    def test_player_sheet_does_not_receive_companion_real_level_authority(self):
        reference, uid, character_id = 14891, 9001, 42
        slot = RULES[reference]["slots"][0]
        character = {
            "id": character_id,
            "level": 200,
            "effective_level": 200,
            "inventory_items": [
                {
                    "uid": uid,
                    "character_id": character_id,
                    "reference": reference,
                    "quantity": 1,
                }
            ],
        }
        sheet = proto_field(10, proto_field(8, uid) + proto_field(16, slot))
        with self.assertRaisesRegex(ValueError, "not implemented"):
            validate_sheet(character, sheet)


if __name__ == "__main__":
    unittest.main()
