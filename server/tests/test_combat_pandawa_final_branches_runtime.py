"""Actual Pandawa transparency and nearby-recipient passive consequences."""
import os
import random
import struct
import unittest
from copy import deepcopy
from unittest.mock import patch

import test_combat_pandawa_runtime as solo
import test_combat_pandawa_carry_death_runtime as shared


@unittest.skipUnless(
    os.environ.get("WAKFU_TEST_GRANTEDCAST") == "1", "native runtime opt-in"
)
class PandawaFinalBranchesRuntimeTests(unittest.TestCase):
    def cast_shared(self, fight, characters, decks, reference, target, action):
        from wakfu_server.combat_server_spell import prepare_server_spell
        from wakfu_server.combat_spell_grant import granted_spells

        uid = (
            granted_spells(fight, 7)
            .get(reference, {})
            .get("uid", (7 << 32) | reference)
        )
        return prepare_server_spell(
            struct.pack(">qqiih", 7, uid, *target),
            characters[7],
            {},
            fight,
            3,
            decks[7],
            action_id=action,
            line_of_sight=lambda *args: True,
            critical=False,
            rng=random.Random(0),
            player_characters=characters,
            deck_blobs=decks,
        ).fight

    def test_barrel_wisdom_actual_transparency_changes_native_cast_los(self):
        helper = solo.PandawaRuntimeTests()
        for passive in (None, 5152):
            with self.subTest(passive=passive):
                fixture = helper.fixture(
                    () if passive is None else (passive,),
                    actives=(4702,),
                    target_distance=3,
                )
                born = helper.cast(fixture, 4718, target=(-7, -7, -1))
                fixture = helper.adopt(fixture, born.fight)
                barrel = next(
                    a
                    for a in born.fight.actors.values()
                    if getattr(a, "native_summon_source", None)
                )
                from wakfu_server.combat_server_spell import server_runtime
                from wakfu_server.combat_casting_los import native_casting_ray

                character, monster, fight, deck, rng = fixture
                _, adapter = server_runtime(
                    character, {-7: monster}, deck, action_id=3, critical=False, rng=rng
                )
                properties = adapter.actor_authority.properties(fight, barrel)
                self.assertEqual(54 in properties, passive == 5152)
                source, target = fight.actors[7], fight.actors[-7]
                visible = native_casting_ray(
                    fight,
                    adapter.actor_authority,
                    character["map_id"],
                    source.position,
                    target.position,
                    source_height=source.native_los_height,
                    target_height=target.native_los_height,
                    ignored_slots=(
                        *fight.native_qi_visibility_ignored_slots,
                        source.native_obstacle_id,
                    ),
                )
                self.assertEqual(visible, passive == 5152)
                if passive is None:
                    with self.assertRaisesRegex(ValueError, "twG"):
                        helper.cast(fixture, 4702, target=target.position, action_id=3)
                else:
                    cast = helper.cast(
                        fixture, 4702, target=target.position, action_id=3
                    )
                    self.assertLess(cast.fight.actors[-7].hp, target.hp)

    def test_aggressive_barrel_end_distributes_tipsy_to_real_nearby_recipients(self):
        from wakfu_server import combat_server_spell

        helper = shared.PandawaCarryDeathRuntimeTests()
        for passive in (None, 4725):
            with self.subTest(passive=passive):
                fight, characters, decks = helper.fixture(
                    carrier_level=200,
                    carried_level=200,
                    pandawa_passives=() if passive is None else (passive,),
                    positions={7: (-8, -7, -1), 8: (-7, -6, -1), 9: (-6, -7, -1)},
                )
                fight = helper.reach(fight, characters, decks, 7)
                fight = self.cast_shared(
                    fight, characters, decks, 4718, (-7, -7, -1), 10
                )
                barrel = next(
                    a
                    for a in fight.actors.values()
                    if getattr(a, "native_summon_source", None)
                )
                observed = []
                original = combat_server_spell.prepare_server_turn_end

                def observe_end(*args, **kwargs):
                    result = original(*args, **kwargs)
                    if kwargs["actor_id"] == 7:
                        observed.append(deepcopy(result[0]))
                    return result

                with patch.object(
                    combat_server_spell, "prepare_server_turn_end", observe_end
                ):
                    helper.reach(fight, characters, decks, 8)
                self.assertEqual(len(observed), 1)
                end = observed[0]
                self.assertEqual(end.actors[barrel.id].hp == 0, passive == 4725)
                for identity in (8, 9):
                    self.assertEqual(
                        6107
                        in {
                            s.reference
                            for s in end.actors[identity].state_ledger.entries
                        },
                        passive == 4725,
                        (identity, passive),
                    )
                self.assertNotIn(
                    6107,
                    {s.reference for s in end.actors[barrel.id].state_ledger.entries},
                )

    def test_pandaperitivo_throw_distributes_tipsy_to_adjacent_ally_and_enemy(self):
        helper = shared.PandawaCarryDeathRuntimeTests()
        for passive in (None, 8600):
            with self.subTest(passive=passive):
                fight, characters, decks = helper.fixture(
                    carrier_level=200,
                    carried_level=200,
                    pandawa_passives=() if passive is None else (passive,),
                    pandawa_actives=(4705,),
                    positions={7: (-8, -7, -1), 8: (-7, -6, -1), 9: (-6, -7, -1)},
                )
                fight = helper.reach(fight, characters, decks, 7)
                fight = self.cast_shared(
                    fight, characters, decks, 4718, (-9, -7, -1), 10
                )
                barrel = next(
                    a
                    for a in fight.actors.values()
                    if getattr(a, "native_summon_source", None)
                )
                self.assertEqual(
                    9368 in {s.reference for s in barrel.state_ledger.entries},
                    passive == 8600,
                )
                # The real constructor itself activates Pandaperitivo and its
                # restriction. Wait for its actual clock before testing throw.
                fight = helper.reach(fight, characters, decks, 8)
                fight = helper.reach(fight, characters, decks, 7)
                self.assertNotIn(
                    9368,
                    {s.reference for s in fight.actors[barrel.id].state_ledger.entries},
                )
                fight = self.cast_shared(
                    fight, characters, decks, 6847, barrel.position, 11
                )
                self.assertNotIn(
                    9368,
                    {s.reference for s in fight.actors[barrel.id].state_ledger.entries},
                )
                from wakfu_server.combat_effect_dispatch import EffectDispatcher
                from wakfu_server.combat_effect_resolver import NativeEffectResolver

                original = EffectDispatcher.execute
                original_candidates = NativeEffectResolver.candidate_invocations
                trace = []

                def observe_candidates(resolver, effect, invocation, **kwargs):
                    result = original_candidates(resolver, effect, invocation, **kwargs)
                    if invocation.reference == 418445:
                        contexts = resolver.native_context(effect, invocation)
                        trace.append(
                            (
                                "selection",
                                [
                                    (
                                        actor.id,
                                        actor.position,
                                        {
                                            key: contexts[actor.id].get(key)
                                            for key in (
                                                "dTE",
                                                "dpu_id",
                                                "baG",
                                                "baK",
                                                "bcN",
                                            )
                                        },
                                    )
                                    for actor in resolver.actors(effect, invocation)
                                ],
                                [row.target_id for row in result],
                            )
                        )
                    return result

                def observe(dispatcher, invocation, **kwargs):
                    result = original(dispatcher, invocation, **kwargs)
                    if invocation.reference in (418445, 418446, 418447, 418448):
                        trace.append(
                            (
                                invocation.reference,
                                invocation.caster_id,
                                invocation.target_id,
                                invocation.cell,
                                invocation.native_preselected_target,
                                invocation.native_explicit_target,
                                invocation.wakemu_fresh_child_selection,
                                result,
                            )
                        )
                    return result

                with patch.object(EffectDispatcher, "execute", observe), patch.object(
                    NativeEffectResolver, "candidate_invocations", observe_candidates
                ):
                    fight = self.cast_shared(
                        fight, characters, decks, 4705, (-7, -7, -1), 12
                    )
                self.assertEqual(fight.actors[barrel.id].position, (-7, -7, -1))
                for identity in (8, 9):
                    self.assertEqual(
                        6107
                        in {
                            s.reference
                            for s in fight.actors[identity].state_ledger.entries
                        },
                        passive == 8600,
                        (
                            identity,
                            passive,
                            trace,
                            [
                                event
                                for event in fight.events
                                if event.get("type") == "state_applied"
                                and event.get("state") == 6107
                            ],
                        ),
                    )
                self.assertEqual(
                    9368
                    in {
                        s.reference
                        for s in fight.actors[barrel.id].state_ledger.entries
                    },
                    passive == 8600,
                )
