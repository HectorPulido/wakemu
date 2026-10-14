"""Native quest dance actors remain distinct from ordinary Bilbyboy combat."""
import json
from pathlib import Path
import tempfile
import unittest

from wakfu_server.maps.monster_minigame_policy import (
    MINIGAME_BLOCKED_REFERENCES,
    QUEST_MINIGAME_BLOCKED_REFERENCES,
    effective_inventory,
    effective_minigame_references,
    exclusion_reason,
    require_ordinary_spawn,
)
from monster_activation_exceptions import exclusion_status
from prepare_monster_spell_activation import select_candidates
from finalize_monster_spell_activation import finalize


class DjQuestMinigamePolicyTests(unittest.TestCase):
    def test_installed_native_quest_and_colored_abilities_identify_exact_actors(self):
        proof = json.loads(
            (
                Path(__file__).parent / "fixtures" / "native_dj_dance_quest1264.json"
            ).read_text()
        )
        self.assertEqual(proof["references"], [2502, 2518])
        quest = proof["native_quest_definition"]
        self.assertEqual(quest["d"], 1264)
        self.assertEqual([row["d"] for row in quest["cjJ"]], [2393])
        self.assertEqual(quest["cjP"], 85)
        self.assertIn(
            "dancing and beatboxing",
            proof["native_quest_text"]["en"]["content.63.1264"],
        )
        self.assertEqual(set(proof["native_area_labels"]), {"527", "528", "529", "530"})
        self.assertEqual(
            proof["consumer_owned_spell_ids"],
            [3701, 3702, 3703, 3704, 3713, 3714, 3715, 3716],
        )
        self.assertEqual(
            proof["native_profiles"]["2518"]["initial_state_triples"], [1895, 1, 1]
        )
        self.assertEqual(
            proof["native_profiles"]["2502"]["native_abilities"],
            [{"level_parameter": -1, "spell_id": 3700}],
        )
        self.assertTrue(
            all(
                row["matches"]
                for row in proof["quest_producer_current_hash_verification"]
            )
        )

    def test_effective_policy_extends_baseline_without_replacing_its_inventory(self):
        self.assertEqual(len(MINIGAME_BLOCKED_REFERENCES), 9)
        self.assertEqual(QUEST_MINIGAME_BLOCKED_REFERENCES, {2502, 2518})
        self.assertEqual(len(effective_minigame_references()), 11)
        inventory = effective_inventory()
        self.assertEqual(len(inventory), 12)
        self.assertEqual(
            sum(row["reason"] == "minigame_requires_encounter" for row in inventory), 11
        )
        for reference in (2502, 2518):
            self.assertEqual(exclusion_status(reference), "blocked_minigame")
            with self.assertRaisesRegex(ValueError, "native minigame encounter"):
                require_ordinary_spawn(reference)
            self.assertIsNone(exclusion_reason(reference, context="native_summon"))

    def test_ordinary_bilbyboy_variants_are_not_excluded_by_name_or_family(self):
        for reference in (2465, 2467, 2519, 2520):
            self.assertIsNone(exclusion_reason(reference))
            require_ordinary_spawn(reference)

    def test_preparation_and_old_finalizer_candidate_cannot_bypass_quest_policy(self):
        rows = [
            dict(
                ref=reference,
                status="covered",
                spell_ids=[1],
                data_gaps=[],
                missing_families=[],
                min_level=85,
                max_level=85,
            )
            for reference in (2502, 2518, 2465)
        ]
        self.assertEqual(
            [row["ref"] for row in select_candidates({"monsters": rows}, 30000)], [2465]
        )
        self.assertEqual(len(rows), 3)
        for reference in (2502, 2518):
            with tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                (root / "manifest.json").write_text(
                    json.dumps({"selected_references": [reference]})
                )
                with self.assertRaisesRegex(
                    ValueError, "explicitly blocked references"
                ):
                    finalize(root, root / "absent.json", root / "output")
                self.assertFalse((root / "output").exists())
