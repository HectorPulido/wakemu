"""Aniripsa passive consequences through real Ready snapshots and owned casts.

The baseline's seventeen unobserved reactions include native marker-only roots.
These tests assert mechanics, rather than treating passive registration as proof.
"""
import os
import unittest

import test_aniripsa_allied_healing_runtime as allied
from wakfu_server.combat_diagnostics import combat_diagnostic_scope


@unittest.skipUnless(
    os.environ.get("WAKFU_TEST_GRANTEDCAST") == "1", "native runtime opt-in"
)
class AniripsaPassivePipelineTests(unittest.TestCase):
    fixture = allied.AniripsaAlliedHealingTests.fixture
    cast = allied.AniripsaAlliedHealingTests.cast

    @classmethod
    def setUpClass(cls):
        from wakfu_server.combat_retained_runtime import native_retained_metadata

        cls.active_retained_metadata = native_retained_metadata()

    def heal_amount(self, passives, target):
        diagnostics = []
        fight, characters, monster, decks = self.fixture(
            level=200, injury=300, passive_spells=passives
        )
        original_hp = fight.actors[target].hp
        with combat_diagnostic_scope(lambda **event: diagnostics.append(event)):
            result = self.cast(fight, characters, monster, decks, 779, target)
        self.assertEqual(fight.actors[target].hp, original_hp)
        self.assertEqual(result.fight.actors[7].ap, fight.actors[7].ap - 3)
        return result.fight.actors[target].hp - original_hp, diagnostics

    def test_paroxismo_vital_changes_received_self_heal_live_runner(self):
        baseline, _ = self.heal_amount((), 7)
        boosted, diagnostics = self.heal_amount((1536,), 7)
        self.assertEqual((baseline, boosted), (42, 54))
        self.assertTrue(
            any(
                event.get("effect_reference") == 371574
                and event.get("status") == "completed"
                for event in diagnostics
            )
        )

    def test_paroxismo_vital_does_not_boost_healing_sent_to_other_actor(self):
        baseline, _ = self.heal_amount((), 8)
        equipped, diagnostics = self.heal_amount((1536,), 8)
        self.assertEqual(equipped, baseline)
        self.assertFalse(
            any(
                event.get("effect_reference") == 371574
                and event.get("status") == "completed"
                for event in diagnostics
            )
        )

    def test_todos_para_mi_installs_exact_vitality_without_heal_accumulation(self):
        baseline, _, _, _ = self.fixture(level=200, injury=300)
        fight, characters, monster, decks = self.fixture(
            level=200, injury=300, passive_spells=(5453,)
        )
        actor = fight.actors[7]
        bonuses = [s for s in actor.state_ledger.entries if s.reference == 8032]
        self.assertEqual(len(bonuses), 1)
        self.assertEqual(bonuses[0].level, 1600)
        self.assertEqual(actor.max_hp - baseline.actors[7].max_hp, 1600)
        self.assertEqual(actor.hp - baseline.actors[7].hp, 1600)
        result = self.cast(fight, characters, monster, decks, 779, 7)
        after = result.fight.actors[7]
        self.assertEqual(after.max_hp, actor.max_hp)
        self.assertEqual(
            [
                (s.reference, s.level)
                for s in after.state_ledger.entries
                if s.reference == 8032
            ],
            [(8032, 1600)],
        )

    def test_elixir_de_viento_consumes_real_positive_tackle_at_fight_start(self):
        arguments = dict(
            level=200,
            caster_aptitudes=((27, 2), (21, 2)),
        )
        baseline, _, _, _ = self.fixture(**arguments)
        diagnostics = []
        with combat_diagnostic_scope(lambda **event: diagnostics.append(event)):
            fight, _, _, _ = self.fixture(passive_spells=(7993,), **arguments)
        self.assertEqual(baseline.actors[7].effect_stats[7], 8)
        self.assertEqual(fight.actors[7].effect_stats[7], 0)
        self.assertEqual(
            fight.actors[7].effect_stats[8], baseline.actors[7].effect_stats[8]
        )
        self.assertTrue(
            any(
                event.get("effect_reference") == 371832
                and event.get("status") == "completed"
                for event in diagnostics
            )
        )

    def test_elixir_zero_tackle_does_not_create_a_negative_characteristic(self):
        fight, _, _, _ = self.fixture(level=200, passive_spells=(7993,))
        self.assertEqual(fight.actors[7].effect_stats[7], 0)
        self.assertFalse(
            any(
                row.get("effect_class") == 174
                for row in fight.owned_stat_effects.values()
            )
        )

    def test_marker_passives_scale_actual_healing_accumulator(self):
        cases = (((), 40), ((7994,), 20), ((7997,), 80), ((7994, 7997), 40))
        for passives, expected_level in cases:
            with self.subTest(passives=passives):
                fight, characters, monster, decks = self.fixture(
                    level=200, injury=300, passive_spells=passives
                )
                result = self.cast(fight, characters, monster, decks, 779, 7)
                self.assertEqual(
                    [
                        (s.reference, s.level)
                        for s in result.fight.actors[7].state_ledger.entries
                        if s.reference in (3869, 3878)
                    ],
                    [(3869, expected_level)],
                )

    def test_direct_attack_consumes_actual_accumulator_and_passive_branches(self):
        cases = (
            ((), 165, None),
            ((628,), 125, None),
            ((644,), 165, 167935),
            ((5463,), 155, 368124),
            ((7994,), 145, 371840),
            ((7995,), 125, 371907),
            ((7997,), 205, 167935),
            ((7993,), 165, 371836),
        )
        for passives, expected_damage, expected_branch in cases:
            with self.subTest(passives=passives):
                fight, characters, monster, decks = self.fixture(
                    level=200,
                    injury=300,
                    active_spells=(779, 630),
                    passive_spells=passives,
                    enemy_position=(-10, -7, -1),
                )
                healed = self.cast(fight, characters, monster, decks, 779, 7).fight
                before_hp = healed.actors[-7].hp
                own_hp = healed.actors[7].hp
                dodge = healed.actors[7].effect_stats[8]
                diagnostics = []
                with combat_diagnostic_scope(lambda **event: diagnostics.append(event)):
                    result = self.cast(healed, characters, monster, decks, 630, -7)
                self.assertEqual(
                    before_hp - result.fight.actors[-7].hp, expected_damage
                )
                own_states = result.fight.actors[7].state_ledger.entries
                self.assertNotIn(3869, [s.reference for s in own_states])
                if passives == (628,):
                    self.assertEqual(
                        [
                            (s.reference, s.level)
                            for s in own_states
                            if s.reference == 3878
                        ],
                        [(3878, 40)],
                    )
                if passives == (5463,):
                    self.assertGreater(result.fight.actors[7].hp, own_hp)
                if passives == (7995,):
                    # Native371906 selects3886 on odd tables;371907 selects3907
                    # on even tables. Ready now publishes the actual first round.
                    odd_table = healed.native_table_turn % 2 == 1
                    expected_branch = 371906 if odd_table else 371907
                    self.assertIn(
                        3886 if odd_table else 3907,
                        [
                            s.reference
                            for s in result.fight.actors[-7].state_ledger.entries
                        ],
                    )
                if passives == (7993,):
                    self.assertGreater(dodge, 0)
                    self.assertEqual(result.fight.actors[7].effect_stats[8], 0)
                    self.assertIn(
                        3903,
                        [
                            s.reference
                            for s in result.fight.actors[-7].state_ledger.entries
                        ],
                    )
                if expected_branch is not None:
                    self.assertTrue(
                        any(
                            e.get("effect_reference") == expected_branch
                            and e.get("status") == "completed"
                            for e in diagnostics
                        )
                    )
