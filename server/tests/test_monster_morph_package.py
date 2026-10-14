"""Focused morphology source-package preservation regressions."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "server/tools"))
from export_monster_morph_profiles import NAMES, package_document


class NativeMorphPackageTests(unittest.TestCase):
    def setUp(self):
        self.source = (
            ROOT
            / ".runtime/monster-low50-20261013/lifecycle/morph933-export/supplement"
        )
        if not self.source.exists():
            self.skipTest("Source-qualified private morphology bundle is unavailable")
        self.manifest = json.loads((self.source / "receipt.json").read_text())[
            "base_sha256"
        ]

    def test_atomic_copied_package_retains_source_proof(self):
        docs = package_document(self.source, self.manifest, root=ROOT)
        self.assertEqual(set(docs), set(NAMES))
        with tempfile.TemporaryDirectory(dir=ROOT / ".runtime") as name:
            directory = Path(name)
            for filename, data in docs.items():
                (directory / filename).write_bytes(data)
            self.assertEqual(
                package_document(directory, self.manifest, root=ROOT), docs
            )
            profiles = json.loads((directory / NAMES[0]).read_text())
            profiles["profiles"]["5900"]["minimum_level"] = 1
            (directory / NAMES[0]).write_text(json.dumps(profiles))
            with self.assertRaises(ValueError):
                package_document(directory, self.manifest, root=ROOT)

    def test_wrong_original_base_rejected(self):
        manifest = dict(self.manifest)
        manifest[NAMES[0]] = "0" * 64
        with self.assertRaises(ValueError):
            package_document(self.source, manifest, root=ROOT)
