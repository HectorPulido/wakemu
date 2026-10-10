"""Exact guide heading identity extraction regressions."""
import importlib.util
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location(
    "boss_identity_tool",
    Path(__file__).parents[1] / "tools/extract_dungeon_boss_identity.py",
)
tool = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tool)


class BossIdentityExtractionTests(unittest.TestCase):
    def extract(self, text, pool=None, names=None):
        with tempfile.TemporaryDirectory() as directory:
            Path(directory, "article.txt").write_text(text)
            inventory = {
                "records": [
                    {
                        "key": "native:1",
                        "guides": [
                            {
                                "source": {
                                    "archive_directory": directory,
                                    "url": "https://example.test/guide",
                                }
                            }
                        ],
                        "native_species_pool": [
                            {"ref_id": ref} for ref in (pool or [1, 2])
                        ],
                    }
                ]
            }
            native = {
                "source": {"key_contract": "native name"},
                "monsters": names
                or [{"ref": 1, "name_fr": "Royal Tofu"}, {"ref": 2, "name_fr": "Tofu"}],
            }
            return tool.extract(inventory, native)["records"][0]

    def test_exact_heading_resolves_and_records_evidence(self):
        row = self.extract("Introduction\n2.4 – Royal Tofu (Boss)\n")
        self.assertEqual(row["boss_references"], [1])
        self.assertEqual(row["evidence"][0]["line"], 2)
        self.assertEqual(len(row["evidence"][0]["article_sha256"]), 64)

    def test_prose_substring_and_partial_name_do_not_resolve(self):
        for text in (
            "Royal Tofu is the Boss",
            "2.4 – Royal Tofu Warrior (Boss)",
            "2.4 – royal tofu (Boss)",
        ):
            self.assertEqual(self.extract(text)["boss_references"], [])

    def test_names_outside_native_pool_do_not_resolve(self):
        self.assertEqual(
            self.extract("2.4 – Royal Tofu (Boss)", pool=[2])["boss_references"], []
        )

    def test_duplicate_native_name_is_ambiguous(self):
        names = [
            {"ref": 1, "name_fr": "Royal Tofu"},
            {"ref": 2, "name_fr": "Royal Tofu"},
        ]
        self.assertEqual(
            self.extract("2.4 – Royal Tofu (Boss)", names=names)["boss_references"], []
        )

    def test_multiple_distinct_boss_headings_remain_unresolved(self):
        row = self.extract("2.4 – Royal Tofu (Boss)\n2.5 – Tofu (Boss)")
        self.assertEqual(row["boss_references"], [])
        self.assertEqual(len(row["evidence"]), 2)


if __name__ == "__main__":
    unittest.main()
