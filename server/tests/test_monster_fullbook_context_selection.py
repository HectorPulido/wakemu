"""Receipt selector preserves owner, native PL and bounded level authority."""
import gzip
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).parents[1] / "tools"))
from select_monster_fullbook_contexts import select_exact_fullbooks


class FullbookSelectionTests(unittest.TestCase):
    def fixture(self, root, *, initial=None, actual_ref=7, actual_pl=2, maximum=3):
        inventory = root / "native.json.gz"
        with gzip.open(inventory, "wt") as handle:
            json.dump(
                {
                    "monsters": [
                        {
                            "ref": 7,
                            "name": "Native actor",
                            "min_level": 1,
                            "max_level": 3,
                            "abilities": [
                                {
                                    "spell_id": 10,
                                    "level_parameter": -1,
                                    "effective_level_range": [1, 3],
                                }
                            ],
                            "raw_native": {"cle": initial or []},
                        }
                    ]
                },
                handle,
            )
        receipt = root / "receipt.json"
        receipt.write_text(
            json.dumps(
                {
                    "sources_stable": True,
                    "cases": [
                        {
                            "context": {
                                "reference": actual_ref,
                                "actor_level": 2,
                                "spell_id": 10,
                                "spell_level": actual_pl,
                            },
                            "raw_case": {
                                "level": 2,
                                "spell_id": 10,
                                "spell_level": actual_pl,
                                "status": "validated",
                                "initialization_receipts": [],
                            },
                        }
                    ],
                }
            )
        )
        digest = hashlib.sha256(receipt.read_bytes()).hexdigest()
        casting = root / "native-spell-casting.json"
        casting.write_text(json.dumps({"10": {"maximum_level": maximum}}))
        index = root / "index.json"
        index.write_text(
            json.dumps(
                {
                    "input_sha256": {
                        str(casting): hashlib.sha256(casting.read_bytes()).hexdigest()
                    },
                    "actual_case_cache": [
                        {
                            "context_ref": digest,
                            "reference": 7,
                            "actor_level": 2,
                            "spell_id": 10,
                            "spell_level": actual_pl,
                            "original_json_pointer": "/cases/0",
                        }
                    ],
                    "receipt_contexts": {
                        digest: {
                            "receipt": str(receipt),
                            "sha256": digest,
                            "source_root": str(root),
                            "candidate_manifest_sha256": "seal",
                        }
                    },
                    "effective_minigame_references": [],
                }
            )
        )
        live = root / "live.json"
        live.write_text('{"activation_policy":{"enabled_monsters":{}}}')
        return dict(
            root=Path(__file__).parents[2],
            index_path=index,
            native_inventory_path=inventory,
            live_catalog_path=live,
        )

    def test_only_actual_proven_native_level_is_selected(self):
        with tempfile.TemporaryDirectory() as name:
            result = select_exact_fullbooks(**self.fixture(Path(name)))
        row = result["actual_ai_queue"][0]
        self.assertEqual(row["native_range"], [1, 3])
        self.assertEqual(row["proven_range"], [2, 2])
        self.assertFalse(row["full_native_max_claim"])
        self.assertFalse(result["admission"])

    def test_actual_native_casting_maximum_caps_actor_level(self):
        with tempfile.TemporaryDirectory() as name:
            result = select_exact_fullbooks(
                **self.fixture(Path(name), actual_pl=1, maximum=1)
            )
        self.assertEqual(result["actual_ai_queue"][0]["original_owned_book"], [(10, 1)])

    def test_different_original_owner_cannot_be_rebound(self):
        with tempfile.TemporaryDirectory() as name:
            arguments = self.fixture(Path(name), actual_ref=8)
            with self.assertRaisesRegex(ValueError, "owner/level"):
                select_exact_fullbooks(**arguments)

    def test_wrong_native_spell_level_or_missing_constructor_is_not_ready(self):
        for options in ({"actual_pl": 1}, {"initial": [20, 1, 0]}):
            with self.subTest(options=options), tempfile.TemporaryDirectory() as name:
                result = select_exact_fullbooks(**self.fixture(Path(name), **options))
                self.assertEqual(result["actual_ai_queue"], [])


if __name__ == "__main__":
    unittest.main()
