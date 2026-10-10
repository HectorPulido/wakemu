"""Aniripsa utility and air consequences through owned native spell transactions."""
import os
import random
import struct
import unittest

import test_aniripsa_allied_healing_runtime as allied


@unittest.skipUnless(
    os.environ.get("WAKFU_TEST_GRANTEDCAST") == "1", "native runtime opt-in"
)
class AniripsaUtilityPipelineTests(unittest.TestCase):
    fixture = allied.AniripsaAlliedHealingTests.fixture
    setUpClass = allied.AniripsaAlliedHealingTests.__dict__["setUpClass"]

    def cast(self, fixture, spell, target, *, critical=False, rng=None):
        from wakfu_server.combat_server_spell import prepare_server_spell

        fight, characters, monster, decks = fixture
        return prepare_server_spell(
            struct.pack(">qqiih", 7, (7 << 32) | spell, *fight.actors[target].position),
            characters[7],
            {-7: monster},
            fight,
            3,
            decks[7],
            action_id=10,
            line_of_sight=lambda *args: True,
            critical=critical,
            rng=rng or random.Random(0),
            player_characters=characters,
            deck_blobs=decks,
        )

    def make(self, spell, *, injury=300, enemy_position=(-10, -7, -1), **kwargs):
        return self.fixture(
            active_spells=(spell,),
            level=200,
            injury=injury,
            enemy_position=enemy_position,
            **kwargs
        )

    def assert_payment_and_source(self, fixture, transaction, before):
        from wakfu_server.fight_checkpoint_store import snapshot

        fight = fixture[0]
        self.assertEqual(snapshot(fight), before)
        self.assertEqual(
            transaction.fight.actors[7].ap,
            fight.actors[7].ap - transaction.plan["costs"]["ap"],
        )
        self.assertEqual(
            transaction.fight.actors[7].effect_stats[4],
            fight.actors[7].effect_stats[4] - transaction.plan["costs"]["wp"],
        )

    def test_juventud_installs_scaled_state_and_actual_maximum_mp_bonus(self):
        from wakfu_server.fight_checkpoint_store import snapshot

        fixture = self.make(782)
        before = snapshot(fixture[0])
        result = self.cast(fixture, 782, 7)
        states = [
            s
            for s in result.fight.actors[7].state_ledger.entries
            if s.reference == 3870
        ]
        self.assertEqual([s.level for s in states], [600])
        self.assertEqual(result.fight.actors[7].mp, fixture[0].actors[7].mp + 2)
        self.assert_payment_and_source(fixture, result, before)

    def test_self_forbidden_utility_rejection_preserves_snapshot_and_rng(self):
        from wakfu_server.fight_checkpoint_store import snapshot

        for spell in (623, 1532, 1533, 1538, 1540, 1541, 1542):
            with self.subTest(spell=spell):
                fixture = self.make(spell)
                before = snapshot(fixture[0])
                rng = random.Random(0)
                original_rng = rng.getstate()
                with self.assertRaises(ValueError):
                    self.cast(fixture, spell, 7, rng=rng)
                self.assertEqual(snapshot(fixture[0]), before)
                self.assertEqual(rng.getstate(), original_rng)

    def test_colimador_damage_and_collision_carrier_are_normal_critical_branches(self):
        from wakfu_server.fight_checkpoint_store import snapshot

        for critical, damage, state_level in ((False, 50, 25), (True, 62, 31)):
            with self.subTest(critical=critical):
                fixture = self.make(623)
                before = snapshot(fixture[0])
                result = self.cast(fixture, 623, -7, critical=critical)
                target = result.fight.actors[-7]
                self.assertEqual(target.hp, fixture[0].actors[-7].hp - damage)
                self.assertEqual(
                    [
                        s.level
                        for s in target.state_ledger.entries
                        if s.reference == 8019
                    ],
                    [state_level],
                )
                self.assert_payment_and_source(fixture, result, before)

    def test_infusion_and_vivification_heal_bounded_allies_and_damage_enemies(self):
        from wakfu_server.fight_checkpoint_store import snapshot

        for spell, healing, damage, resistance in (
            (1532, 31, 100, 0),
            (1533, 33, 54, 40),
        ):
            for target in (8, -7):
                with self.subTest(spell=spell, target=target):
                    fixture = self.make(spell)
                    fight = fixture[0]
                    before = snapshot(fight)
                    result = self.cast(fixture, spell, target)
                    actor = result.fight.actors[target]
                    self.assertEqual(
                        actor.hp - fight.actors[target].hp,
                        healing if target == 8 else -damage,
                    )
                    self.assertLessEqual(actor.hp, actor.max_hp)
                    if target == 8:
                        self.assertEqual(
                            actor.effect_stats[32]
                            - fight.actors[target].effect_stats[32],
                            2,
                        )
                        self.assertEqual(
                            actor.effect_stats[8]
                            - fight.actors[target].effect_stats[8],
                            resistance,
                        )
                    self.assert_payment_and_source(fixture, result, before)

    def test_desfase_reduces_actual_ap_and_repeat_criterion_cannot_reapply(self):
        from wakfu_server.fight_checkpoint_store import snapshot

        fixture = self.make(627)
        before = snapshot(fixture[0])
        result = self.cast(fixture, 627, 8)
        actor = result.fight.actors[8]
        self.assertEqual(actor.ap, 0)
        self.assertEqual(
            {s.reference for s in actor.state_ledger.entries} & {3896, 3897},
            {3896, 3897},
        )
        self.assert_payment_and_source(fixture, result, before)
        second_fixture = (result.fight, *fixture[1:])
        repeat_before = snapshot(result.fight)
        rng = random.Random(0)
        rng_before = rng.getstate()
        with self.assertRaisesRegex(ValueError, "casting eligibility rejected: twV"):
            self.cast(second_fixture, 627, 8, rng=rng)
        self.assertEqual(snapshot(result.fight), repeat_before)
        self.assertEqual(rng.getstate(), rng_before)

    def test_prohibicion_selects_fragile_or_incurable_from_real_contra_natura(self):
        from wakfu_server.combat_server_spell import prepare_server_spell
        from wakfu_server.fight_checkpoint_store import snapshot

        for converted, expected in ((False, 6624), (True, 756)):
            with self.subTest(converted=converted):
                fixture = self.make(1538)
                if converted:
                    fight, characters, monster, decks = fixture
                    toggle = prepare_server_spell(
                        struct.pack(">qqiih", 7, 7977, *fight.actors[7].position),
                        characters[7],
                        {-7: monster},
                        fight,
                        3,
                        decks[7],
                        action_id=9,
                        line_of_sight=lambda *a: True,
                        critical=False,
                        rng=random.Random(0),
                        player_characters=characters,
                        deck_blobs=decks,
                    )
                    fixture = (toggle.fight, *fixture[1:])
                before = snapshot(fixture[0])
                result = self.cast(fixture, 1538, -7)
                self.assertEqual(
                    [
                        s.level
                        for s in result.fight.actors[-7].state_ledger.entries
                        if s.reference == expected
                    ],
                    [5],
                )
                self.assertNotIn(
                    756 if expected == 6624 else 6624,
                    {s.reference for s in result.fight.actors[-7].state_ledger.entries},
                )
                self.assert_payment_and_source(fixture, result, before)

    def test_infected_flask_damages_and_installs_scaled_gangrene(self):
        from wakfu_server.fight_checkpoint_store import snapshot

        fixture = self.make(1542)
        before = snapshot(fixture[0])
        result = self.cast(fixture, 1542, -7)
        self.assertEqual(result.fight.actors[-7].hp, fixture[0].actors[-7].hp - 84)
        self.assertEqual(
            [
                s.level
                for s in result.fight.actors[-7].state_ledger.entries
                if s.reference == 3876
            ],
            [84],
        )
        self.assert_payment_and_source(fixture, result, before)

    def test_caster_clock_collision_carrier_expires_at_real_next_turn(self):
        from combat_audit_turns import advance_actual_turn
        from wakfu_server.combat_runtime_messages import RuntimeMessages
        from wakfu_server.combat_server_spell import (
            prepare_server_turn_end,
            prepare_server_turn_start,
            server_runtime,
        )

        fixture = self.make(623)
        result = self.cast(fixture, 623, -7)
        _, characters, monster, decks = fixture
        rng = random.Random(0)
        common = dict(player_characters=characters, deck_blobs=decks, rng=rng)
        runtime = RuntimeMessages(
            result.fight,
            turn_end_provider=lambda p, **kw: prepare_server_turn_end(
                characters[7], {-7: monster}, p, decks[7], **common, **kw
            ),
            turn_start_provider=lambda p, **kw: prepare_server_turn_start(
                characters[7], {-7: monster}, p, decks[7], **common, **kw
            ),
            expiration_runtime_factory=lambda *, action_id: server_runtime(
                characters[7],
                {-7: monster},
                decks[7],
                action_id=action_id,
                critical=False,
                **common
            )[0],
        )
        for _ in range(8):
            advance_actual_turn(runtime)
            if runtime.fight.current.id == 7:
                break
        self.assertEqual(runtime.fight.current.id, 7)
        self.assertNotIn(
            8019, {s.reference for s in runtime.fight.actors[-7].state_ledger.entries}
        )

    def test_aletargamiento_selects_real_caster_health_threshold(self):
        from wakfu_server.fight_checkpoint_store import snapshot

        for injury, expected_damage in ((300, 189), (1500, 135)):
            with self.subTest(injury=injury):
                fixture = self.make(1541, injury=injury)
                actor = fixture[0].actors[7]
                self.assertEqual(actor.hp * 100 >= actor.max_hp * 80, injury == 300)
                before = snapshot(fixture[0])
                result = self.cast(fixture, 1541, -7)
                self.assertEqual(
                    fixture[0].actors[-7].hp - result.fight.actors[-7].hp,
                    expected_damage,
                )
                self.assert_payment_and_source(fixture, result, before)

    def test_utility_healing_caps_and_received_healing_resistance_rounding(self):
        from wakfu_server.fight_checkpoint_store import snapshot

        for spell in (1532, 1533):
            with self.subTest(spell=spell):
                fixture = self.make(spell, injury=1)
                before = snapshot(fixture[0])
                result = self.cast(fixture, spell, 8)
                self.assertEqual(result.fight.actors[8].hp, fixture[0].actors[8].max_hp)
                self.assertEqual(
                    result.fight.actors[8].effect_stats[32],
                    fixture[0].actors[8].effect_stats[32],
                )
                if spell == 1533:
                    self.assertEqual(
                        result.fight.actors[8].effect_stats[8]
                        - fixture[0].actors[8].effect_stats[8],
                        40,
                    )
                self.assert_payment_and_source(fixture, result, before)

    def test_psicosis_at_native_range_reduces_final_damage_and_ferocity(self):
        from wakfu_server.fight_checkpoint_store import snapshot

        for critical, expected_damage in ((False, 69), (True, 86)):
            with self.subTest(critical=critical):
                fixture = self.make(1540, enemy_position=(-11, -7, -1))
                before = snapshot(fixture[0])
                result = self.cast(fixture, 1540, -7, critical=critical)
                original, target = fixture[0].actors[-7], result.fight.actors[-7]
                self.assertEqual(original.hp - target.hp, expected_damage)
                self.assertEqual(
                    target.effect_stats[48], original.effect_stats[48] - 20
                )
                self.assertEqual(target.effect_stats[9], original.effect_stats[9] - 20)
                self.assert_payment_and_source(fixture, result, before)
