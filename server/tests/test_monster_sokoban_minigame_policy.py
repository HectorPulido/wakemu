import unittest
from wakfu_server.monster_minigame_policy import (
    MINIGAME_BLOCKED_REFERENCES,
    QUEST_MINIGAME_BLOCKED_REFERENCES,
    SOKOBAN_MINIGAME_BLOCKED_REFERENCES,
    effective_minigame_references,
    exclusion_reason,
    require_ordinary_spawn,
)
from prepare_monster_spell_activation import select_candidates


class SokobanMinigamePolicyTests(unittest.TestCase):
    def test_exact_source_scope_blocks_ordinary_but_not_native_summon(self):
        self.assertEqual(SOKOBAN_MINIGAME_BLOCKED_REFERENCES, {3891, 4113, 5030})
        for ref in SOKOBAN_MINIGAME_BLOCKED_REFERENCES:
            self.assertEqual(exclusion_reason(ref), "minigame_requires_encounter")
            with self.assertRaisesRegex(ValueError, "native minigame"):
                require_ordinary_spawn(ref)
            self.assertIsNone(exclusion_reason(ref, context="native_summon"))

    def test_original_baseline_and_quest_constants_preserved(self):
        self.assertEqual(
            MINIGAME_BLOCKED_REFERENCES,
            {2782, 2784, 3217, 3893, 3896, 3897, 3942, 3943, 3944},
        )
        self.assertEqual(QUEST_MINIGAME_BLOCKED_REFERENCES, {2502, 2518})
        self.assertEqual(len(effective_minigame_references()), 14)

    def test_unrelated_admin_test_and_disguise_remain_allowed(self):
        for ref in (3070, 3118, 3021):
            self.assertIsNone(exclusion_reason(ref))
            require_ordinary_spawn(ref)

    def test_preparation_skips_only_blocked_rows_and_preserves_input(self):
        refs = [3891, 4113, 5030, 3070]
        rows = [
            dict(
                ref=ref,
                status="covered",
                spell_ids=[7],
                data_gaps=[],
                missing_families=[],
                min_level=1,
                max_level=5,
            )
            for ref in refs
        ]
        self.assertEqual(
            [r["ref"] for r in select_candidates(dict(monsters=rows), maximum=50)],
            [3070],
        )
        self.assertEqual([r["ref"] for r in rows], refs)
