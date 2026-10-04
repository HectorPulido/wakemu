"""Fail when native planting inputs are omitted from deploy artifacts."""
import hashlib
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class PlantingPackageTests(unittest.TestCase):
    def test_manifest_and_docker_include_current_native_inputs(self):
        entries = {
            r["path"]: r
            for r in json.loads((ROOT / "protocol/content-manifest.json").read_text())[
                "catalogs"
            ]
        }
        docker = (ROOT / "Dockerfile").read_text()
        for name in (
            "seed-actions.json",
            "plant-resources.json",
            "ecology-regions.json",
            "planting-maps/index.json",
        ):
            path = "protocol/" + name
            self.assertEqual(
                entries[path]["sha256"],
                hashlib.sha256((ROOT / path).read_bytes()).hexdigest(),
            )
            self.assertIn(
                "protocol/" + ("planting-maps" if "/" in name else name), docker
            )
        index = json.loads((ROOT / "protocol/planting-maps/index.json").read_text())
        self.assertTrue(index)
