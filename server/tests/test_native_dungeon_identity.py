import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import zipfile


spec = importlib.util.spec_from_file_location(
    "native_identity",
    Path(__file__).parents[1] / "tools/apply_native_dungeon_identity.py",
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class NativeIdentityTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.definition = {"id": 90, "raw_aHA": [1086], "raw_arM": 527}
        self.document = {
            "dungeon": {
                "slug": "guide",
                "client_definition_id": None,
                "client_template_id": None,
                "client_asset_map_id": None,
            },
            "source": {"url": "https://example.test/guide"},
            "rooms": [{"order": 1}],
        }
        self.composition = self.write("composition.json", self.document)
        self.write("definitions.json", [self.definition])
        self.write("catalog.json", {"dungeons": [self.document]})
        self.routes = self.write(
            "routes.json",
            [
                {
                    "definition_id": 90,
                    "template_id": 777,
                    "entry_map_id": 527,
                    "start_map_id": 1086,
                }
            ],
        )
        with zipfile.ZipFile(self.root / "i18n.jar", "w") as archive:
            archive.writestr("texts_fr.properties", "content.137.90=Native")
        self.index = {
            "name_contract": "content.137.<id>",
            "sources": {
                key: {"path": filename, "sha256": module.digest(self.root / filename)}
                for key, filename in [
                    ("definitions", "definitions.json"),
                    ("catalog", "catalog.json"),
                    ("i18n", "i18n.jar"),
                ]
            },
            "guide_links": [
                {
                    "guide_slug": "guide",
                    "guide_url": "https://example.test/guide",
                    "status": "exact_unique",
                    "client_definition_id": 90,
                    "exact_names_checked": ["Native"],
                    "candidates": [dict(self.definition, name_fr="Native")],
                }
            ],
        }

    def write(self, name, value):
        path = self.root / name
        path.write_text(json.dumps(value))
        return path

    def prepare(self):
        return module.prepare(
            self.root, self.index, self.routes, self.composition, "guide"
        )

    def test_template_comes_from_route_not_definition_increment(self):
        updated, report = self.prepare()
        self.assertEqual(updated["dungeon"]["client_template_id"], 777)
        self.assertEqual(updated["rooms"], self.document["rooms"])
        self.assertFalse(report["runtime_imported"])

    def test_stale_source_hash_rejected(self):
        self.write("definitions.json", [])
        with self.assertRaises(ValueError):
            self.prepare()

    def test_ambiguous_route_rejected(self):
        routes = json.loads(self.routes.read_text())
        self.write("routes.json", routes + routes)
        with self.assertRaises(ValueError):
            self.prepare()

    def test_missing_route_rejected(self):
        self.write("routes.json", [])
        with self.assertRaises(ValueError):
            self.prepare()

    def test_changed_composition_rejected(self):
        self.write("composition.json", dict(self.document, rooms=[]))
        with self.assertRaises(ValueError):
            self.prepare()

    def test_route_map_conflict_rejected(self):
        route = json.loads(self.routes.read_text())[0]
        route["start_map_id"] = 2000
        self.write("routes.json", [route])
        with self.assertRaises(ValueError):
            self.prepare()


if __name__ == "__main__":
    unittest.main()
