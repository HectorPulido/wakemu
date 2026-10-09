import importlib.util
from pathlib import Path
import unittest


spec = importlib.util.spec_from_file_location(
    "native_dungeon_index",
    Path(__file__).parents[1] / "tools/export_native_dungeon_index.py",
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class NativeDungeonIndexTests(unittest.TestCase):
    def link(self, names, title="Exact Dungeon Niv.21", reviewed="Exact Dungeon"):
        definitions = [
            {"id": identity, "raw_aHA": [100 + identity]} for identity in names
        ]
        properties = "\n".join(
            f"content.137.{identity}={name}" for identity, name in names.items()
        )
        guides = {
            "dungeons": [
                {
                    "source": {"url": "https://example.test/guide"},
                    "dungeon": {"name": reviewed, "slug": "guide"},
                }
            ]
        }
        canonical = {
            "guides": [{"canonical_url": "https://example.test/guide", "title": title}]
        }
        return module.export_index(definitions, properties, guides, canonical)[
            "guide_links"
        ][0]

    def test_exact_unique_preserves_native_map_evidence(self):
        link = self.link({1: "Exact Dungeon"})
        self.assertEqual(link["status"], "exact_unique")
        self.assertEqual(link["client_definition_id"], 1)
        self.assertEqual(link["candidates"][0]["raw_aHA"], [101])

    def test_duplicate_name_remains_ambiguous(self):
        link = self.link({1: "Exact Dungeon", 2: "Exact Dungeon"})
        self.assertEqual(link["status"], "ambiguous")
        self.assertIsNone(link["client_definition_id"])

    def test_case_or_punctuation_differences_are_not_guessed(self):
        self.assertEqual(self.link({1: "exact dungeon"})["status"], "unmatched")
        self.assertEqual(self.link({1: "Exact-Dungeon"})["status"], "unmatched")

    def test_display_suffix_is_only_removed_at_end(self):
        self.assertEqual(module.strip_level_suffix("Name Niv.21"), "Name")
        self.assertEqual(
            module.strip_level_suffix("Name Niv.21 Extra"), "Name Niv.21 Extra"
        )


if __name__ == "__main__":
    unittest.main()
