"""Actual opposing player hit against source-owned Tipsy/Pandemic."""
import os
import random
import struct
import unittest
from unittest.mock import patch
import test_combat_pandawa_carry_death_runtime as shared_fixture


@unittest.skipUnless(
    os.environ.get("WAKFU_TEST_GRANTEDCAST") == "1", "native runtime opt-in"
)
class PandawaPandemicRuntimeTests(unittest.TestCase):
    fixture = shared_fixture.PandawaCarryDeathRuntimeTests.fixture
    reach = shared_fixture.PandawaCarryDeathRuntimeTests.reach

    def test_pandemic_reduces_real_tipsy_enemy_attack_only_when_equipped(self):
        from wakfu_server.combat_server_spell import prepare_server_spell
        from wakfu_server.combat_spell_grant import granted_spells
        from wakfu_server import combat_final_modifier

        damage = {}
        for passive in (None, 5151):
            with self.subTest(passive=passive):
                fight, characters, decks = self.fixture(
                    carrier_level=200,
                    carried_level=200,
                    pandawa_passives=() if passive is None else (passive,),
                    attacker_spell=4780,
                )
                fight = self.reach(fight, characters, decks, 7)
                tipsy = prepare_server_spell(
                    struct.pack(
                        ">qqiih",
                        7,
                        granted_spells(fight, 7)[8592]["uid"],
                        *fight.actors[9].position
                    ),
                    characters[7],
                    {},
                    fight,
                    3,
                    decks[7],
                    action_id=10,
                    line_of_sight=lambda *args: True,
                    critical=False,
                    rng=random.Random(0),
                    player_characters=characters,
                    deck_blobs=decks,
                )
                self.assertIn(
                    6107,
                    {
                        entry.reference
                        for entry in tipsy.fight.actors[9].state_ledger.entries
                    },
                )
                fight = self.reach(tipsy.fight, characters, decks, 9)
                before = fight.actors[7].hp
                added = []
                original = combat_final_modifier.NativeFinalModifier.add

                def observe(modifier, amount):
                    added.append(amount)
                    return original(modifier, amount)

                with patch.object(
                    combat_final_modifier.NativeFinalModifier, "add", observe
                ):
                    hit = prepare_server_spell(
                        struct.pack(
                            ">qqiih", 9, (9 << 32) | 4780, *fight.actors[7].position
                        ),
                        characters[9],
                        {},
                        fight,
                        5,
                        decks[9],
                        action_id=11,
                        line_of_sight=lambda *args: True,
                        critical=False,
                        rng=random.Random(0),
                        player_characters=characters,
                        deck_blobs=decks,
                    )
                damage[passive] = before - hit.fight.actors[7].hp
                self.assertGreater(damage[passive], 0)
                if passive == 5151:
                    self.assertIn(-20, added)
                else:
                    self.assertNotIn(-20, added)
        self.assertLess(damage[5151], damage[None])

    def test_owned_tipsy_outgoing_bonus_is_excluded_by_pandemic(self):
        from wakfu_server.combat_server_spell import prepare_server_spell
        from wakfu_server.combat_spell_grant import granted_spells
        from wakfu_server.combat_effect_dispatch import EffectDispatcher
        from wakfu_server import combat_final_modifier

        damage = {}
        for passive in (None, 5151):
            with self.subTest(passive=passive):
                fight, characters, decks = self.fixture(
                    carrier_level=200,
                    carried_level=200,
                    pandawa_passives=() if passive is None else (passive,),
                    pandawa_actives=(4704,),
                    attacker_distance=2,
                )
                fight = self.reach(fight, characters, decks, 7)
                tipsy = prepare_server_spell(
                    struct.pack(
                        ">qqiih",
                        7,
                        granted_spells(fight, 7)[8592]["uid"],
                        *fight.actors[9].position
                    ),
                    characters[7],
                    {},
                    fight,
                    3,
                    decks[7],
                    action_id=10,
                    line_of_sight=lambda *args: True,
                    critical=False,
                    rng=random.Random(0),
                    player_characters=characters,
                    deck_blobs=decks,
                )
                listeners = [
                    row
                    for row in tipsy.fight.native_owned_group_effects.values()
                    if row["invocation"]["reference"] == 417589
                ]
                before = tipsy.fight.actors[9].hp
                added, calls = [], []
                original_add = combat_final_modifier.NativeFinalModifier.add
                original_execute = EffectDispatcher.execute
                original_activation = EffectDispatcher.execute_activation

                def add(modifier, amount):
                    added.append(amount)
                    return original_add(modifier, amount)

                def observe(original):
                    def run(dispatcher, invocation, **kwargs):
                        result = original(dispatcher, invocation, **kwargs)
                        if invocation.reference in (417589, 417590):
                            calls.append(
                                (
                                    invocation.reference,
                                    invocation.caster_id,
                                    invocation.target_id,
                                    result,
                                    invocation.native_trigger_context,
                                )
                            )
                        return result

                    return run

                with patch.object(
                    combat_final_modifier.NativeFinalModifier, "add", add
                ), patch.object(
                    EffectDispatcher, "execute", observe(original_execute)
                ), patch.object(
                    EffectDispatcher, "execute_activation", observe(original_activation)
                ):
                    hit = prepare_server_spell(
                        struct.pack(
                            ">qqiih",
                            7,
                            (7 << 32) | 4704,
                            *tipsy.fight.actors[9].position
                        ),
                        characters[7],
                        {},
                        tipsy.fight,
                        3,
                        decks[7],
                        action_id=11,
                        line_of_sight=lambda *args: True,
                        critical=False,
                        rng=random.Random(0),
                        player_characters=characters,
                        deck_blobs=decks,
                    )
                damage[passive] = before - hit.fight.actors[9].hp
                self.assertGreater(damage[passive], 0)
                self.assertEqual(
                    20 in added,
                    passive is None,
                    dict(listeners=listeners, calls=calls, modifiers=added),
                )
        self.assertLess(damage[5151], damage[None])
