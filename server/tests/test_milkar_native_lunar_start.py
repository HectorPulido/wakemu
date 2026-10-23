"""Milkar's actual constructor chooses its native initial lunar branch at1003."""
import unittest
from unittest.mock import patch


class MilkarNativeLunarStartTests(unittest.TestCase):
    def test_constructor_grade_one_earns_new_moon_and_next_grade_at_real_start(self):
        from xelor_multiowner_fixture import TwoXelorFixture
        from wakfu_server.combat_effect_dispatch import EffectDispatcher
        from wakfu_server import combat_server_spell
        from wakfu_server.combat_npc_initialization import initial_plans
        from wakfu_server.combat_qi_fight import current_registry

        before, calls = [], []
        original_initialize = combat_server_spell.prepare_server_initialization
        original_execute = EffectDispatcher.execute

        def initialize(character, monsters, fight, *args, **kwargs):
            if not before:
                actor = fight.actors[-7]
                before.append(
                    dict(
                        states=[
                            (entry.reference, entry.level)
                            for entry in actor.state_ledger.entries
                        ],
                        hp=actor.hp,
                        maximum=actor.max_hp,
                    )
                )
            return original_initialize(character, monsters, fight, *args, **kwargs)

        def execute(dispatcher, invocation, *args, **kwargs):
            if invocation.reference in (
                332325,
                332326,
                332328,
                332329,
                332331,
                332332,
                332334,
                332335,
            ):
                calls.append(
                    (invocation.reference, invocation.caster_id, invocation.target_id)
                )
            return original_execute(dispatcher, invocation, *args, **kwargs)

        with patch.object(
            combat_server_spell, "prepare_server_initialization", initialize
        ), patch.object(EffectDispatcher, "execute", execute):
            fight, characters, monster, decks = TwoXelorFixture().fixture(
                level=200,
                caster_breed=8,
                second_player_breed=8,
                active_spells=(4780,),
                second_player_spells=(4780,),
                compact_arena=False,
                native_target_ref=1987,
                native_target_level=95,
            )
        self.assertEqual(
            initial_plans(fight, {-7: monster})[-7][:2],
            (1987, (5619, 1, 0, 7318, 1, 1)),
        )
        self.assertIn((7318, 1), before[0]["states"])
        self.assertNotIn(7317, {ref for ref, _ in before[0]["states"]})
        self.assertEqual([ref for ref, _, _ in calls], [332325, 332326])
        self.assertTrue(all(caster == target == -7 for _, caster, target in calls))
        actor = fight.actors[-7]
        states = {
            (entry.reference, entry.level) for entry in actor.state_ledger.entries
        }
        self.assertIn((7317, 1), states)
        self.assertIn((7318, 2), states)
        self.assertFalse({7315, 7316, 7319} & {ref for ref, _ in states})
        self.assertTrue(fight.native_start_event_delivered)
        self.assertEqual(
            (actor.hp, actor.max_hp), (before[0]["hp"], before[0]["maximum"])
        )
        self.assertEqual(actor.effective_level, 95)
        self.assertFalse(actor.controlled)
        self.assertEqual(
            {a.owner_id for a in fight.actors.values() if a.controlled}, {3, 4, 5}
        )
        current_registry(fight)


if __name__ == "__main__":
    unittest.main()
