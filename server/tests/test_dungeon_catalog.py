import copy
from dataclasses import FrozenInstanceError
import json
from pathlib import Path
import tempfile
import unittest

from wakfu_server.maps.dungeon_catalog import (
    compile_catalog,
    compile_document,
    write_import_plan,
)


class DungeonCatalogTests(unittest.TestCase):
    def setUp(self):
        self.document = dict(
            schema_version=1,
            dungeon=dict(
                slug="example",
                client_definition_id=1,
                client_template_id=2,
                client_asset_map_id=3,
            ),
            source=dict(
                url="https://example.org",
                article_sha256="0" * 64,
                client_version_match="unverified",
            ),
            extraction=dict(reviewed=True),
            rooms=[
                dict(
                    order=1,
                    composition_status="complete",
                    monsters=[
                        dict(
                            name="Example",
                            ref_id=4,
                            count=2,
                            min_level=None,
                            max_level=None,
                            role="monster",
                        )
                    ],
                )
            ],
        )
        self.native = [dict(ref=4, min_level=8, max_level=12)]

    def compile(self):
        return compile_document(self.document, self.native)

    def test_native_range_compiles_without_inventing_grade(self):
        plan = self.compile()
        self.assertTrue(plan.roster_ready)
        self.assertEqual(8, plan.rooms[0].monsters[0].native_min_level)
        self.assertIsNone(plan.rooms[0].monsters[0].guide_min_level)
        self.assertFalse(plan.import_record()["runtime_ready"])

    def test_unknown_count_retained_without_executable_roster(self):
        self.document["rooms"][0]["monsters"][0]["count"] = None
        self.assertFalse(self.compile().roster_ready)

    def test_unknown_reference_is_not_matched_by_name(self):
        self.document["rooms"][0]["monsters"][0]["ref_id"] = None
        self.assertIn(
            "monster[0].unresolved_reference", self.compile().rooms[0].diagnostics
        )

    def test_absent_native_reference_is_diagnostic(self):
        self.native = []
        self.assertIn(
            "monster[0].absent_native_reference", self.compile().rooms[0].diagnostics
        )

    def test_boolean_count_and_negative_reference_rejected(self):
        for field, value in [("count", True), ("ref_id", -1)]:
            with self.subTest(field=field):
                original = self.document["rooms"][0]["monsters"][0][field]
                self.document["rooms"][0]["monsters"][0][field] = value
                with self.assertRaises(ValueError):
                    self.compile()
                self.document["rooms"][0]["monsters"][0][field] = original

    def test_duplicate_room_rejected(self):
        self.document["rooms"].append(copy.deepcopy(self.document["rooms"][0]))
        with self.assertRaises(ValueError):
            self.compile()

    def test_missing_room_blocks_whole_roster(self):
        self.document["rooms"][0]["order"] = 2
        self.assertFalse(self.compile().roster_ready)

    def test_unreviewed_or_mismatching_version_blocks(self):
        self.document["extraction"]["reviewed"] = False
        self.assertFalse(self.compile().roster_ready)
        self.document["extraction"]["reviewed"] = True
        self.document["source"]["client_version_match"] = "mismatch"
        self.assertFalse(self.compile().roster_ready)

    def test_roster_immutable_and_detached_from_input(self):
        plan = self.compile()
        self.document["rooms"][0]["monsters"][0]["count"] = 9
        self.assertEqual(2, plan.rooms[0].monsters[0].count)
        with self.assertRaises(FrozenInstanceError):
            plan.slug = "changed"

    def test_duplicate_dungeon_rejected(self):
        with self.assertRaises(ValueError):
            compile_catalog([self.document, self.document], self.native)

    def test_draft_persistence_preserves_diagnostics_and_source_digest(self):
        self.document["rooms"][0]["monsters"][0]["count"] = None
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "plan.json"
            write_import_plan(target, compile_catalog([self.document], self.native))
            row = json.loads(target.read_text())["dungeons"][0]
            self.assertEqual("0" * 64, row["source_sha256"])
            self.assertFalse(row["roster_ready"])
            self.assertFalse(target.with_suffix(".json.tmp").exists())
