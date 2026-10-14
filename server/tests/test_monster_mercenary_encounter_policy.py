import unittest
from wakfu_server.monster_minigame_policy import (
    MERCENARY_MINIGAME_BLOCKED_REFERENCES,
    exclusion_reason,
    require_ordinary_spawn,
)


class MercenaryEncounterPolicyTests(unittest.TestCase):
    def test_exact_source_proven_actors_require_encounter_but_keep_native_summon(self):
        self.assertEqual(MERCENARY_MINIGAME_BLOCKED_REFERENCES, {4794, 4838})
        for ref in MERCENARY_MINIGAME_BLOCKED_REFERENCES:
            with self.assertRaises(ValueError):
                require_ordinary_spawn(ref)
            self.assertIsNone(exclusion_reason(ref, context="native_summon"))

    def test_unrelated_monster_and_admin_variants_remain_eligible(self):
        for ref in (4175, 2444, 2446, 3072):
            self.assertIsNone(exclusion_reason(ref))
            require_ordinary_spawn(ref)
