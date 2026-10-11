"""Source-bound element PC documents append without replacing shared data."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from export_monster_spell_element_damage_pcs import (
    CATALOG_PATH,
    EXPORTER,
    JAR,
    package_document,
    validate_document,
)


class SpellElementPCPackageTests(unittest.TestCase):
    def native_document(self):
        return json.loads(
            (
                Path(__file__).parent
                / "fixtures/monster_spell_element_damage_pcs_native.json"
            ).read_text()
        )

    def test_append_identical_keep_conflict_and_source_drift(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in (JAR, EXPORTER):
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(name.encode())
            document = root / CATALOG_PATH
            document.write_text(json.dumps(self.native_document()))
            digest = hashlib.sha256(document.read_bytes()).hexdigest()
            receipt = dict(
                schema="native-spell-element-damage-pcs-export-v1",
                document_sha256=digest,
                element_count=8,
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
            (root / EXPORTER).write_bytes(b"changed")
            with self.assertRaisesRegex(ValueError, "installed source proof"):
                package_document(document, {}, root=root)

    def test_native_identity_null_authority_and_pc_domain_reject_malformed(self):
        changes = [
            lambda d: d.update(source="unknown"),
            lambda d: d.update(null_pc_present=None),
            lambda d: d["elements"].pop("9"),
            lambda d: d["elements"]["1"].update(native_element=True),
            lambda d: d["elements"]["1"].update(native_element=2),
            lambda d: d["elements"]["1"].update(element_name="PHYSICAL"),
            lambda d: d["elements"]["1"].update(damage_stat=True),
            lambda d: d["elements"]["1"].update(damage_stat=128),
            lambda d: d["elements"]["1"].update(damage_stat=22),
            lambda d: d["elements"]["0"].pop("damage_stat"),
        ]
        for mutate in changes:
            document = deepcopy(self.native_document())
            mutate(document)
            with self.subTest(document=document), self.assertRaises(ValueError):
                validate_document(document)

    def test_sealed_native_null_and_elemental_population_stays_exact(self):
        document = validate_document(self.native_document())
        self.assertIsNone(document["elements"]["0"]["damage_stat"])
        self.assertIsNone(document["elements"]["9"]["damage_stat"])
        self.assertEqual(
            {
                r["damage_stat"]
                for r in document["elements"].values()
                if r["damage_stat"] is not None
            },
            {21, 22, 23, 24, 90, 109},
        )
