"""Actual cat action pays its own resources and isolates allied recipients."""
import os
import struct
import unittest
from unittest.mock import patch

import test_ecaflip_summon_ability_pipeline as ability_fixture


@unittest.skipUnless(
    os.environ.get("WAKFU_TEST_GRANTEDCAST") == "1", "native runtime opt-in"
)
class EcaflipCatActionConsequencesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        ability_fixture.EcaflipSummonAbilityPipelineTests.setUpClass()

    def test_actual_cat_debuff_pays_cat_once_and_preserves_other_actors(self):
        from wakfu_server import combat_server_spell

        original = combat_server_spell.prepare_server_spell
        observed = []

        def inspect_actual_cast(request, *args, **kwargs):
            actor_id, spell_uid, _x, _y, _z = struct.unpack(">qqiih", request)
            fight = args[2]
            if spell_uid != 5231:
                return original(request, *args, **kwargs)
            before = {
                identity: dict(
                    hp=actor.hp,
                    ap=actor.ap,
                    mp=actor.mp,
                    effect_stats=dict(actor.effect_stats),
                )
                for identity, actor in fight.actors.items()
            }
            result = original(request, *args, **kwargs)
            observed.append((actor_id, before, result))
            return result

        # Reuse the actual draw/creation/turn producer, not a fabricated actor
        # or injected final debuff. Its original assertions also execute.
        helper = ability_fixture.EcaflipSummonAbilityPipelineTests()
        with patch.object(
            combat_server_spell, "prepare_server_spell", inspect_actual_cast
        ):
            helper.test_miaumiau_owned_ability_debuffs_marked_enemy_near_actual_controller()
        self.assertEqual(len(observed), 1)
        cat_id, before, result = observed[0]
        self.assertNotEqual(cat_id, 7)
        cat = result.fight.actors[cat_id]
        self.assertEqual(cat.ap, before[cat_id]["ap"] - result.plan["costs"]["ap"])
        self.assertEqual(cat.mp, before[cat_id]["mp"] - result.plan["costs"]["mp"])
        for identity in (7, 8, 9):
            with self.subTest(unrelated_actor=identity):
                actor = result.fight.actors[identity]
                self.assertEqual(actor.hp, before[identity]["hp"])
                self.assertEqual(actor.ap, before[identity]["ap"])
                self.assertEqual(actor.mp, before[identity]["mp"])
                self.assertEqual(actor.effect_stats, before[identity]["effect_stats"])
                self.assertFalse(
                    any(state.reference == 7957 for state in actor.state_ledger.entries)
                )
        enemy_states = [
            state
            for state in result.fight.actors[-7].state_ledger.entries
            if state.reference == 7957
        ]
        self.assertEqual(sum(state.level for state in enemy_states), 120)
