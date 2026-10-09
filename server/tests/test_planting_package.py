"""Fail when native planting inputs are omitted from deploy artifacts."""
import hashlib
import json
import unittest
from pathlib import Path
from wakfu_server import native_catalog

ROOT = Path(__file__).resolve().parents[1]


class PlantingPackageTests(unittest.TestCase):
    def test_manifest_and_docker_include_current_native_inputs(self):
        entries = {
            r["path"]: r
            for r in json.loads(
                native_catalog.read_text(ROOT / "protocol/content-manifest.json")
            )["catalogs"]
        }
        docker = native_catalog.read_text(ROOT / "Dockerfile")
        for name in (
            "seed-actions.json",
            "plant-resources.json",
            "ecology-regions.json",
            "planting-maps/index.json",
        ):
            path = "protocol/" + name
            self.assertEqual(
                entries[path]["sha256"],
                hashlib.sha256(native_catalog.read_bytes(ROOT / path)).hexdigest(),
            )
            self.assertIn(
                "protocol/" + ("planting-maps" if "/" in name else name), docker
            )
        index = json.loads(
            native_catalog.read_text(ROOT / "protocol/planting-maps/index.json")
        )
        self.assertTrue(index)
