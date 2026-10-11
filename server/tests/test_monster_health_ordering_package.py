"""Native health identity artifacts append only after installed-source proof."""
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from export_monster_health_target_ordering import (
    CATALOG_PATH,
    CONTRACT,
    EXPORTER,
    JAR,
    package_document,
    validate_rows,
)


class HealthOrderingPackageTests(unittest.TestCase):
    def test_append_identical_keep_and_existing_conflict_rejection(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in (JAR, EXPORTER):
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(name.encode())
            document = root / CATALOG_PATH
            document.write_text(
                json.dumps(
                    {
                        "123": dict(
                            effect_class=330,
                            native_effect_flags=[8, 26],
                            maximum_targets=-1,
                            ordering_contract=CONTRACT,
                        )
                    }
                )
            )
            digest = hashlib.sha256(document.read_bytes()).hexdigest()
            receipt = dict(
                schema="native-health-target-ordering-export-v1",
                document_sha256=digest,
                definition_count=1,
                sources={
                    name: hashlib.sha256((root / name).read_bytes()).hexdigest()
                    for name in (JAR, EXPORTER)
                },
            )
            document.with_suffix(".receipt.json").write_text(json.dumps(receipt))
            self.assertEqual(
                package_document(document, {}, root=root),
                {CATALOG_PATH: document.read_bytes()},
            )
            self.assertEqual(
                package_document(document, {CATALOG_PATH: digest}, root=root), {}
            )
            with self.assertRaisesRegex(ValueError, "must not be replaced"):
                package_document(document, {CATALOG_PATH: "different"}, root=root)
            (root / JAR).write_bytes(b"changed")
            with self.assertRaisesRegex(ValueError, "installed source proof"):
                package_document(document, {}, root=root)

    def test_unknown_class_flags_marker_cap_and_reference_reject(self):
        base = dict(
            effect_class=330,
            native_effect_flags=[8],
            maximum_targets=1,
            ordering_contract=CONTRACT,
        )
        for reference, mutation in [
            ("0", {}),
            ("x", {}),
            ("1", {"effect_class": True}),
            ("1", {"native_effect_flags": [8, 8]}),
            ("1", {"native_effect_flags": [26]}),
            ("1", {"ordering_contract": "unknown"}),
            ("1", {"maximum_targets": 128}),
        ]:
            with self.assertRaises(ValueError):
                validate_rows({reference: dict(base, **mutation)})
