"""Remaining Aniripsa passive consequences from legal native spell pipelines."""
import os
import unittest

import test_aniripsa_allied_healing_runtime as allied
import random
from wakfu_server.combat_server_spell import prepare_server_turn_end


@unittest.skipUnless(
    os.environ.get("WAKFU_TEST_GRANTEDCAST") == "1", "native runtime opt-in"
)
class AniripsaRemainingPassiveTests(unittest.TestCase):
    setUpClass = classmethod(allied.AniripsaAlliedHealingTests.setUpClass.__func__)
    fixture = allied.AniripsaAlliedHealingTests.fixture
    cast = allied.AniripsaAlliedHealingTests.cast

    def end_turn(self, fight, characters, monster, decks):
        return prepare_server_turn_end(
            characters[7],
            {-7: monster},
            fight,
            decks[7],
            actor_id=7,
            action_id=30,
            rng=random.Random(0),
            player_characters=characters,
            deck_blobs=decks,
        )[0]

    def test_series_marker_heals_wounded_ring_recipient_on_actual_mark(self):
        for passives, expected in (((), 0), ((1537,), 21)):
            with self.subTest(passives=passives):
                fight, characters, monster, decks = self.fixture(
                    level=200,
                    injury=300,
                    active_spells=(645,),
                    passive_spells=passives,
                    enemy_position=(-10, -7, -1),
                )
                before = fight.actors[7].hp
                result = self.cast(fight, characters, monster, decks, 645, -7).fight
                self.assertEqual(result.actors[7].hp - before, expected)
                self.assertEqual(result.actors[8].hp, fight.actors[8].hp)
                self.assertIn(
                    3882, [s.reference for s in result.actors[-7].state_ledger.entries]
                )
                self.assertEqual(fight.actors[7].hp, before)

    def test_resplandor_consumes_accumulator_and_heals_allies_at_real_turn_end(self):
        for passives, expected in (
            ((), {7: 42, 8: 0, 9: 0}),
            ((7987,), {7: 64, 8: 24, 9: 22}),
        ):
            with self.subTest(passives=passives):
                fight, characters, monster, decks = self.fixture(
                    level=200,
                    injury=300,
                    passive_spells=passives,
                    enemy_position=(-10, -7, -1),
                )
                healed = self.cast(fight, characters, monster, decks, 779, 7).fight
                self.assertIn(
                    3869, [s.reference for s in healed.actors[7].state_ledger.entries]
                )
                ended = self.end_turn(healed, characters, monster, decks)
                self.assertEqual(
                    {i: ended.actors[i].hp - fight.actors[i].hp for i in expected},
                    expected,
                )
                self.assertEqual(ended.actors[-7].hp, fight.actors[-7].hp)
                self.assertEqual(
                    3869 in [s.reference for s in ended.actors[7].state_ledger.entries],
                    not bool(passives),
                )

    def test_presence_rebuilds_real_healing_accumulator_at_turn_regeneration(self):
        for passives, expected_level in (((), 40), ((7990,), 80)):
            with self.subTest(passives=passives):
                fight, characters, monster, decks = self.fixture(
                    level=200,
                    injury=300,
                    passive_spells=passives,
                    enemy_position=(-10, -7, -1),
                )
                healed = self.cast(fight, characters, monster, decks, 779, 7).fight
                ended = self.end_turn(healed, characters, monster, decks)
                self.assertEqual(
                    [
                        (s.reference, s.level)
                        for s in ended.actors[7].state_ledger.entries
                        if s.reference == 3869
                    ],
                    [(3869, expected_level)],
                )
                self.assertEqual(ended.actors[7].hp, healed.actors[7].hp)
                self.assertEqual(ended.actors[-7].hp, fight.actors[-7].hp)

    def test_punction_real_heal_pays_health_only_above_native_threshold(self):
        for passives, injury, expected_cost in (
            ((), 300, 0),
            ((5454,), 300, 4),
            ((5454,), 1000, 0),
        ):
            with self.subTest(passives=passives, injury=injury):
                fight, characters, monster, decks = self.fixture(
                    level=200,
                    injury=injury,
                    passive_spells=passives,
                    enemy_position=(-10, -7, -1),
                )
                result = self.cast(fight, characters, monster, decks, 779, 8).fight
                self.assertEqual(
                    fight.actors[7].hp - result.actors[7].hp, expected_cost
                )
                self.assertEqual(result.actors[8].hp - fight.actors[8].hp, 47)
                self.assertEqual(result.actors[7].ap, fight.actors[7].ap - 3)

    def test_single_heal_passive_requires_real_turn_start_and_direct_heal(self):
        from test_aniripsa_mark_pipeline import AniripsaMarkPipelineTests
        from combat_audit_turns import advance_actual_turn

        helper = AniripsaMarkPipelineTests()
        for passive, expected_heal in ((None, 46), (1415, 115)):
            with self.subTest(passive=passive):
                fixture = helper.fixture(
                    passive=passive, injury=300, active_spells=(779,)
                )
                runtime = fixture[3]
                while runtime.fight.current.id != 7:
                    advance_actual_turn(runtime)
                advance_actual_turn(runtime)
                while runtime.fight.current.id != 7:
                    advance_actual_turn(runtime)
                before = runtime.fight.actors[7].hp
                helper.cast(fixture, 779, 7)
                self.assertEqual(runtime.fight.actors[7].hp - before, expected_heal)

    def test_anbareul_repulsion_consumes_real_mark_without_pushing_target(self):
        import struct
        from test_aniripsa_mark_pipeline import AniripsaMarkPipelineTests
        from wakfu_server.combat_server_spell import prepare_server_spell

        helper = AniripsaMarkPipelineTests()
        fixture = helper.fixture(passive=7996, injury=300, active_spells=(645,))
        character, monsters, deck, runtime, rng = fixture
        helper.cast(fixture, 645, -7)
        before = runtime.fight.actors[-7].hp
        neighbor_hp = runtime.fight.actors[-8].hp
        position = runtime.fight.actors[-7].position
        result = prepare_server_spell(
            struct.pack(">qqiih", 7, 7979, *position),
            character,
            monsters,
            runtime.fight,
            3,
            deck,
            action_id=90,
            rng=rng,
            line_of_sight=lambda *args: True,
            critical=False,
        ).fight
        self.assertEqual(result.actors[-7].hp, before)
        self.assertLess(result.actors[-8].hp, neighbor_hp)
        self.assertEqual(result.actors[-7].position, position)
        self.assertNotIn(
            3882, [s.reference for s in result.actors[-7].state_ledger.entries]
        )
        self.assertIn(
            3882, [s.reference for s in result.actors[-8].state_ledger.entries]
        )
        self.assertIn(
            3882, [s.reference for s in runtime.fight.actors[-7].state_ledger.entries]
        )

    def test_production_secret_delays_real_direct_damage_until_enemy_turn_end(self):
        from test_aniripsa_mark_pipeline import AniripsaMarkPipelineTests
        from combat_audit_turns import advance_actual_turn
        from wakfu_server.combat_diagnostics import combat_diagnostic_scope

        helper = AniripsaMarkPipelineTests()
        fixture = helper.fixture(passive=7995, injury=300, active_spells=(779, 630))
        runtime = fixture[3]
        while runtime.fight.current.id != 7:
            advance_actual_turn(runtime)
        advance_actual_turn(runtime)
        while runtime.fight.current.id != 7:
            advance_actual_turn(runtime)
        helper.cast(fixture, 779, 7)
        helper.cast(fixture, 630, -7)
        before = runtime.fight.actors[-7].hp
        self.assertIn(
            3907, [s.reference for s in runtime.fight.actors[-7].state_ledger.entries]
        )
        events = []
        with combat_diagnostic_scope(lambda **event: events.append(event), limit=16384):
            for _ in range(8):
                previous = runtime.fight.current.id
                advance_actual_turn(runtime)
                if previous == -7:
                    break
        self.assertLess(runtime.fight.actors[-7].hp, before)
        self.assertTrue(
            any(
                e.get("effect_reference") == 371902 and e.get("status") == "completed"
                for e in events
            )
        )
