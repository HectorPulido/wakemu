"""Actual Démence cast retires its native temporary obstacle at spell end."""
from copy import deepcopy
import random
import struct
import unittest
from unittest.mock import patch


class AreaExternalRemovalTests(unittest.TestCase):
    def test_demencia_native_wall_blocks_during_pull_and_retires_at_cast_end(self):
        from test_combat_spell_transaction import SpellTransactionTests
        from wakfu_server.combat_effect_dispatch import EffectDispatcher
        from wakfu_server.combat_server_spell import (
            prepare_server_initialization,
            prepare_server_spell,
        )
        from wakfu_server.spells import encode_deck

        character, monster, fight = SpellTransactionTests().native_server_fixture(
            11,
            200,
            native_qi=True,
            full_health=True,
            target_distance=3,
        )
        deck = encode_deck([5035], [])
        fight, _ = prepare_server_initialization(
            character,
            {-7: monster},
            fight,
            3,
            deck,
            action_id=1,
            rng=random.Random(19),
            fight_start=True,
        )
        cell = (-7, -7, -1)
        self.assertIn(cell, fight.walkable)
        original = EffectDispatcher._execute_scoped
        created = []

        def observe(dispatcher, invocation, **kwargs):
            result = original(dispatcher, invocation, **kwargs)
            if invocation.reference == 353444:
                preview = dispatcher.native_retention.fight
                created.extend(
                    deepcopy(row)
                    for row in preview.native_effect_areas.values()
                    if row.get("effect_reference") == 353444
                )
            return result

        before_ap = fight.actors[7].ap
        with patch.object(EffectDispatcher, "_execute_scoped", observe):
            transaction = prepare_server_spell(
                struct.pack(">qqiih", 7, (7 << 32) | 5035, *cell),
                character,
                {-7: monster},
                fight,
                3,
                deck,
                action_id=2,
                line_of_sight=lambda *args: True,
                critical=True,
                rng=random.Random(19),
            )
        self.assertEqual(len(created), 1)
        area = created[0]
        self.assertEqual(area["reference"], 1605)
        self.assertEqual(tuple(area["cell"]), cell)
        self.assertTrue(area["native_wall_constructor"]["movement_blocking"])
        self.assertFalse(area["keep_after"])
        result = transaction.fight
        self.assertLess(result.actors[7].ap, before_ap)
        self.assertNotIn(area["uid"], result.native_effect_areas)
        self.assertNotIn(area["effect_uid"], result.native_owned_area_effects)
        self.assertNotIn(area["effect_uid"], result.native_retained_records)
        self.assertFalse(
            any(
                slot is not None
                and tuple(slot.get("identity", ())) == ("effect_area", area["uid"])
                for slot in result.native_qi_slots
            )
        )
        # The actual native obstacle has gone: ordinary movement can enter its cell.
        moved = deepcopy(result)
        before_mp = moved.actors[7].mp
        moved.move(3, 7, (cell,))
        self.assertEqual(moved.actors[7].position, cell)
        self.assertLess(moved.actors[7].mp, before_mp)
