"""Actual Ecaflip proximity, healing and card-postcast passive consumers."""
import os
import random
import struct
import unittest
from unittest.mock import patch

import test_combat_aptitude_healing_runtime as allied
import test_ecaflip_hand_passives_pipeline as hand


@unittest.skipUnless(
    os.environ.get("WAKFU_TEST_GRANTEDCAST") == "1", "native runtime opt-in"
)
class EcaflipRemainingPassivesPipelineTests(unittest.TestCase):
    fixture = allied.AptitudeHealingRuntimeTests.fixture
    setUpClass = allied.AptitudeHealingRuntimeTests.__dict__["setUpClass"]

    @staticmethod
    def level(fight, identity, reference):
        return sum(
            row.level
            for row in fight.actors[identity].state_ledger.entries
            if row.reference == reference
        )

    def turn_boundary(self, fight, characters, monster, decks):
        from wakfu_server.combat_server_spell import prepare_server_turn_end

        return prepare_server_turn_end(
            characters[7],
            {-7: monster},
            fight,
            decks[7],
            actor_id=7,
            action_id=30,
            rng=random.Random(7),
            player_characters=characters,
            deck_blobs=decks,
        )[0]

    def test_feline_impact_requires_passive_and_adjacent_enemy_at_actual_turn_end(self):
        from wakfu_server.combat_effect_dispatch import EffectDispatcher

        original = EffectDispatcher.execute
        for passive, adjacent in ((True, True), (True, False), (False, True)):
            with self.subTest(passive=passive, adjacent=adjacent):
                fight, chars, monster, decks = self.fixture(
                    active_spells=(2060,),
                    passive_spells=(5249,) if passive else (),
                    caster_breed=6,
                    level=200,
                    caster_aptitudes=(),
                    enemy_position=(-8, -8, -1) if adjacent else (-5, -7, -1),
                )
                trace = []

                def observe(dispatcher, invocation, **kwargs):
                    result = original(dispatcher, invocation, **kwargs)
                    if invocation.reference == 359219:
                        trace.append(
                            (invocation.caster_id, invocation.target_id, result)
                        )
                    return result

                self.assertEqual(self.level(fight, 7, 7950), 0)
                with patch.object(EffectDispatcher, "execute", observe):
                    after = self.turn_boundary(fight, chars, monster, decks)
                expected = passive and adjacent
                self.assertEqual(self.level(after, 7, 7950), int(expected), trace)
                self.assertEqual(any(row[2] is True for row in trace), expected, trace)
                self.assertEqual(self.level(fight, 7, 7950), 0)

    def test_healing_streak_actual_ally_heal_adds_five_then_regeneration_removes_streak(
        self,
    ):
        from wakfu_server.combat_server_spell import prepare_server_spell
        from wakfu_server.combat_effect_dispatch import EffectDispatcher

        original = EffectDispatcher.execute
        rewards = []

        def observe(dispatcher, invocation, **kwargs):
            result = original(dispatcher, invocation, **kwargs)
            if invocation.reference == 359890 and result is True:
                rewards.append((invocation.caster_id, invocation.target_id))
            return result

        for passive in (False, True):
            with self.subTest(passive=passive):
                fight, chars, monster, decks = self.fixture(
                    active_spells=(2067,),
                    passive_spells=(7954,) if passive else (),
                    caster_breed=6,
                    level=200,
                    caster_aptitudes=(),
                    injury=600,
                )
                before = self.level(fight, 7, 3683)
                hp = fight.actors[8].hp
                observer = patch.object(EffectDispatcher, "execute", observe)
                observer.start()
                self.addCleanup(observer.stop)
                tx = prepare_server_spell(
                    struct.pack(
                        ">qqiih", 7, (7 << 32) | 2067, *fight.actors[8].position
                    ),
                    chars[7],
                    {-7: monster},
                    fight,
                    3,
                    decks[7],
                    action_id=20,
                    line_of_sight=lambda *args: True,
                    critical=False,
                    rng=random.Random(7),
                    player_characters=chars,
                    deck_blobs=decks,
                )
                observer.stop()
                self.assertGreater(tx.fight.actors[8].hp, hp)
                # Compare the same lawful heal: the passive's 8044 carrier adds
                # five per actual eligible heal recipient. Pulga Arcito heals
                # the three injured allied players in this native area fixture.
                delta = self.level(tx.fight, 7, 3683) - before
                if passive:
                    positive = delta
                    ended = self.turn_boundary(tx.fight, chars, monster, decks)
                    self.assertEqual(self.level(ended, 7, 3683), 0)
                else:
                    control = delta
        self.assertEqual(len(rewards), 3, rewards)
        self.assertEqual(positive - control, 5 * len(rewards), rewards)

    def test_feline_tarot_actual_card_postcast_swaps_and_applies_property_only_with_passive(
        self,
    ):
        from wakfu_server.combat_effect_dispatch import EffectDispatcher
        from wakfu_server.combat_property_stack import property_present

        helper = hand.EcaflipHandPassivesPipelineTests()
        original = EffectDispatcher.execute
        for passive in (False, True):
            with self.subTest(passive=passive):
                data = helper.fixture(passives=(7955,) if passive else ())
                trace = []

                def observe(dispatcher, invocation, **kwargs):
                    relevant = invocation.reference in (374216, 374217, 374218, 374219)
                    before_positions = (
                        tuple(
                            dispatcher.actor_position(identity)
                            if identity is not None
                            else None
                            for identity in (invocation.caster_id, invocation.target_id)
                        )
                        if relevant
                        else ()
                    )
                    result = original(dispatcher, invocation, **kwargs)
                    after_positions = (
                        tuple(
                            dispatcher.actor_position(identity)
                            if identity is not None
                            else None
                            for identity in (invocation.caster_id, invocation.target_id)
                        )
                        if relevant
                        else ()
                    )
                    if relevant:
                        trace.append(
                            (
                                invocation.reference,
                                invocation.caster_id,
                                invocation.target_id,
                                result,
                                before_positions,
                                after_positions,
                            )
                        )
                    return result

                from class_spell_eligible_targets import eligible_cast_targets
                from wakfu_server.combat_server_spell import (
                    server_runtime,
                    prepare_server_spell,
                )

                character, monster, fight, deck, rng = data
                _, adapter = server_runtime(
                    character,
                    {-7: monster},
                    deck,
                    action_id=40,
                    critical=False,
                    rng=rng,
                )
                choice = None
                for card in sorted(helper.cards(fight)):
                    candidates = eligible_cast_targets(
                        fight,
                        character,
                        deck,
                        card,
                        adapter=adapter,
                        line_of_sight=lambda *args: True,
                        limit=128,
                        maximum_eligible=16,
                    )
                    cells = [
                        row["target"]
                        for row in candidates["eligible"]
                        if tuple(row["target"]) == fight.actors[-7].position
                    ]
                    if cells:
                        choice = card, cells[0]
                        break
                self.assertIsNotNone(choice, sorted(helper.cards(fight)))
                card, cell = choice
                with patch.object(EffectDispatcher, "execute", observe):
                    tx = prepare_server_spell(
                        struct.pack(">qqiih", 7, card, *cell),
                        character,
                        {-7: monster},
                        fight,
                        3,
                        deck,
                        action_id=40,
                        line_of_sight=lambda *args: True,
                        critical=False,
                        rng=rng,
                    )
                after = character, monster, tx.fight, deck, rng
                swaps = [row for row in trace if row[0] == 374218 and row[3] is True]
                props = [row for row in trace if row[0] == 374219 and row[3] is True]
                self.assertEqual(bool(swaps), passive, (card, trace))
                self.assertEqual(bool(props), passive, (card, trace))
                if passive:
                    self.assertTrue(
                        any(
                            after[2].actors[key].position != actor.position
                            for key, actor in data[2].actors.items()
                        ),
                        (card, cell, trace),
                    )
                    self.assertTrue(
                        any(
                            property_present(actor.native_fight_property_counts, 11)
                            for actor in after[2].actors.values()
                        ),
                        trace,
                    )
