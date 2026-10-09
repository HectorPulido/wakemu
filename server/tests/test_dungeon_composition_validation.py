import copy
import importlib.util
import json
from pathlib import Path
import unittest
from wakfu_server import native_catalog

SERVER_ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "validator", SERVER_ROOT / "tools/validate_dungeon_compositions.py"
)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class DungeonCompositionValidationTests(unittest.TestCase):
    def setUp(self):
        self.schema = json.loads(
            native_catalog.read_text(
                SERVER_ROOT / "protocol/dungeon-room-composition.schema.json"
            )
        )
        evidence = dict(
            source_url="https://example.org/guide/",
            archive_path="article.txt",
            kind="text",
            locator="Room one",
            excerpt="Two monsters",
        )
        monster = dict(
            name="Monster",
            ref_id=None,
            count=2,
            min_level=None,
            max_level=None,
            role="monster",
            evidence=[evidence],
            unknown_fields=["ref_id", "min_level", "max_level"],
        )
        self.document = dict(
            schema_version=1,
            dungeon=dict(
                name="Dungeon",
                slug="dungeon",
                client_definition_id=None,
                client_template_id=None,
                client_asset_map_id=None,
            ),
            source=dict(
                url="https://example.org/guide/",
                archive_directory="guide",
                retrieved_at="2026-10-07T00:00:00Z",
                article_sha256="0" * 64,
                published_at=None,
                updated_at=None,
                game_version=None,
                client_version_match="unverified",
            ),
            extraction=dict(status="complete", method="text", reviewed=False, notes=[]),
            rooms=[
                dict(
                    order=1,
                    label="Room one",
                    composition_status="complete",
                    monsters=[monster],
                    evidence=[evidence],
                    notes=[],
                )
            ],
            unresolved_questions=[],
        )

    def errors(self):
        return MODULE.validate_document(self.document, self.schema)

    def test_known_composition_with_unknown_native_data(self):
        self.assertEqual([], self.errors())

    def test_duplicate_room_order(self):
        self.document["rooms"].append(copy.deepcopy(self.document["rooms"][0]))
        self.assertTrue(any("unique" in e for e in self.errors()))

    def test_maximum_below_minimum(self):
        monster = self.document["rooms"][0]["monsters"][0]
        monster.update(min_level=20, max_level=10, unknown_fields=["ref_id"])
        self.assertTrue(any("minimum level" in e for e in self.errors()))

    def test_missing_unknown_flag(self):
        self.document["rooms"][0]["monsters"][0]["unknown_fields"].remove("ref_id")
        self.assertTrue(any("unknown_fields" in e for e in self.errors()))

    def test_unknown_count_cannot_be_complete(self):
        monster = self.document["rooms"][0]["monsters"][0]
        monster["count"] = None
        monster["unknown_fields"].append("count")
        self.assertTrue(any("unknown count" in e for e in self.errors()))

    def test_evidence_from_other_guide(self):
        self.document["rooms"][0]["evidence"][0][
            "source_url"
        ] = "https://example.org/other/"
        self.assertTrue(any("another guide" in e for e in self.errors()))

    def test_source_must_match_index(self):
        guide = dict(canonical_url="https://example.org/other/", aliases=[])
        self.assertTrue(
            any(
                "indexed guide" in e
                for e in MODULE.validate_document(self.document, self.schema, guide)
            )
        )

    def test_negative_and_text_counts_rejected(self):
        for value in (-1, "2"):
            with self.subTest(value=value):
                self.document["rooms"][0]["monsters"][0]["count"] = value
                self.assertTrue(self.errors())


if __name__ == "__main__":
    unittest.main()
