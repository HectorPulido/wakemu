import unittest
from wakfu_server.monster_minigame_policy import (
    BWORKBALL_MINIGAME_BLOCKED_REFERENCES,
    MINIGAME_BLOCKED_REFERENCES,
    QUEST_MINIGAME_BLOCKED_REFERENCES,
    SOKOBAN_MINIGAME_BLOCKED_REFERENCES,
    exclusion_reason,
    require_ordinary_spawn,
)
from prepare_monster_spell_activation import select_candidates


class BworkballEncounterPolicyTests(unittest.TestCase):
    def test_exact_native_bworkball_scope_keeps_real_summon_route(self):
        self.assertEqual(
            BWORKBALL_MINIGAME_BLOCKED_REFERENCES, {2780, 2789, 2790, 2791}
        )
        for ref in BWORKBALL_MINIGAME_BLOCKED_REFERENCES:
            with self.assertRaises(ValueError):
                require_ordinary_spawn(ref)
            self.assertIsNone(exclusion_reason(ref, context="native_summon"))
        require_ordinary_spawn(2781)

    def test_original_constants_and_candidate_inventory_preserved(self):
        self.assertEqual(len(MINIGAME_BLOCKED_REFERENCES), 9)
        self.assertEqual(QUEST_MINIGAME_BLOCKED_REFERENCES, {2502, 2518})
        self.assertEqual(SOKOBAN_MINIGAME_BLOCKED_REFERENCES, {3891, 4113, 5030})
        refs = [2780, 2789, 2790, 2791, 2781]
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
            [r["ref"] for r in select_candidates(dict(monsters=rows), 50)], [2781]
        )
        self.assertEqual([r["ref"] for r in rows], refs)
