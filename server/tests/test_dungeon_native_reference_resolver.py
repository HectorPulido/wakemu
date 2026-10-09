import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

SPEC = importlib.util.spec_from_file_location(
    "resolver",
    Path(__file__).resolve().parents[1] / "tools/resolve_dungeon_native_references.py",
)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class NativeReferenceResolverTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        (self.root / "compositions").mkdir()
        (self.root / "archive").write_bytes(b"native")
        (self.root / "definitions.json").write_text(
            json.dumps([dict(id=1, raw_cno=[8])])
        )
        self.index = dict(
            sources=dict(
                definitions=dict(
                    path="definitions.json",
                    sha256=MODULE.digest(self.root / "definitions.json"),
                )
            ),
            guide_links=[
                dict(guide_slug="test", status="exact_unique", client_definition_id=1)
            ],
        )
        self.names = dict(
            source=dict(
                archive="archive",
                archive_sha256=MODULE.digest(self.root / "archive"),
                key_contract="content.7",
            ),
            monsters=[dict(ref=8, name_fr="Same"), dict(ref=9, name_fr="Same")],
        )
        (self.root / "compositions/test.json").write_text(
            json.dumps(
                dict(
                    dungeon=dict(slug="test"),
                    rooms=[dict(order=1, monsters=[dict(name="Same")])],
                )
            )
        )

    def report(self):
        return MODULE.build_report(
            self.root,
            self.index,
            self.names,
            native_name_catalog="names.json",
            composition_directory="compositions",
        )

    def test_generic_species_intersection_resolves_ambiguity(self):
        row = self.report()["records"][0]
        self.assertEqual([8, 9], row["exact_name_candidates"])
        self.assertEqual(8, row["resolved_ref"])
        self.assertEqual(1, row["context"]["definition_id"])

    def test_unmatched_dungeon_keeps_ambiguity(self):
        self.index["guide_links"][0]["status"] = "unmatched"
        self.assertEqual("ambiguous", self.report()["records"][0]["status"])

    def test_changed_source_fails_preflight(self):
        (self.root / "archive").write_bytes(b"changed")
        with self.assertRaisesRegex(ValueError, "hash mismatch"):
            self.report()

    def test_casefolded_typography_resolves_with_species_context(self):
        self.names["monsters"][0]["name_fr"] = "same"
        self.names["monsters"][1]["name_fr"] = "same"
        self.assertEqual("resolved", self.report()["records"][0]["status"])

    def test_report_never_changes_composition(self):
        target = self.root / "compositions/test.json"
        before = target.read_bytes()
        self.report()
        self.assertEqual(before, target.read_bytes())

    def test_typography_preserves_accents_words_articles_and_plural(self):
        self.assertEqual(MODULE.normalized_name(" Rat’ Os  Imbibé "), "rat' os imbibé")
        self.assertEqual(
            MODULE.normalized_name("Égare\u0301s"), MODULE.normalized_name("Égarés")
        )
        for left, right in (("Égarés", "Egares"), ("Le Rat", "Rat"), ("Rats", "Rat")):
            self.assertNotEqual(
                MODULE.normalized_name(left), MODULE.normalized_name(right)
            )

    def test_normalization_collision_remains_ambiguous_without_context(self):
        self.index["guide_links"][0]["status"] = "unmatched"
        self.names["monsters"][0]["name_fr"] = "Same"
        self.names["monsters"][1]["name_fr"] = "same"
        row = self.report()["records"][0]
        self.assertEqual("ambiguous", row["status"])
        self.assertEqual([8, 9], row["normalized_name_candidates"])
