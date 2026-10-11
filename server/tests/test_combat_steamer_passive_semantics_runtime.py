"""Steamer native passive branches through lawful Ready, casts and turns."""
import itertools
import os
import unittest
from unittest.mock import patch
import test_combat_steamer_runtime as helpers


@unittest.skipUnless(
    os.environ.get("WAKFU_TEST_GRANTEDCAST") == "1", "native runtime opt-in"
)
class SteamerPassiveSemanticsRuntimeTests(unittest.TestCase):
    def fixture(self, passives=(), *, actives=(), target_distance=3):
        import random
        from test_combat_spell_transaction import SpellTransactionTests
        from wakfu_server.combat_server_spell import prepare_server_initialization
        from wakfu_server.spells import encode_deck

        character, monster, fight = SpellTransactionTests().native_server_fixture(
            16,
            200,
            target_hp=2000,
            native_qi=True,
            target_distance=target_distance,
            variation_seed=17,
        )
        deck = encode_deck(list(actives), passives)
        rng = random.Random(0)
        fight, _ = prepare_server_initialization(
            character,
            {-7: monster},
            fight,
            3,
            deck,
            action_id=1,
            rng=rng,
            fight_start=True,
        )
        return character, monster, fight, deck, rng

    cast = helpers.SteamerRuntimeTests.cast
    adopt = helpers.SteamerRuntimeTests.adopt
    next_owned_turn = helpers.SteamerRuntimeTests.next_owned_turn

    def test_turret_passives_select_actual_cost_range_los_and_linearity(self):
        for short, charged, linear in itertools.product((False, True), repeat=3):
            passives = tuple(
                p
                for p, enabled in ((6928, short), (6932, charged), (7810, linear))
                if enabled
            )
            with self.subTest(passives=passives):
                data = self.fixture(passives)
                self.assertNotIn(
                    7745, {s.reference for s in data[2].actors[7].state_ledger.entries}
                )
                result = self.cast(data, 7700)
                flags = result.plan["native_casting_flags"]
                self.assertEqual(
                    (flags["minimum"], flags["maximum"]), (1, 3 if short else 6)
                )
                self.assertEqual(flags["linear"], linear)
                self.assertEqual(flags["line_of_sight"], not linear)
                self.assertEqual(result.plan["costs"]["wp"], 1 if charged else 0)
                self.assertEqual(
                    sum(
                        bool(getattr(a, "native_summon_source", None))
                        for a in result.fight.actors.values()
                    ),
                    1,
                )

    def test_motor_passive_reduces_real_mp_maximum_and_gives_microbot_capacity(self):
        baseline = self.fixture()
        passive = self.fixture((6934,))
        self.assertEqual(passive[2].actors[7].max_mp, baseline[2].actors[7].max_mp - 1)
        self.assertEqual(passive[2].actors[7].mp, baseline[2].actors[7].mp - 1)
        # Its eight-versus-six placement cap is a native cast criterion,
        # not an extra guessed range modifier.
        for data in (baseline, passive):
            result = self.cast(data, 7008)
            self.assertEqual(
                len(result.fight.native_microbot_networks[7]["microbot_ids"]), 1
            )

    def test_reinforced_armor_uses_actual_level_hp_and_form_turn_loss(self):
        baseline = self.fixture()
        passive = self.fixture((6936,))
        self.assertEqual(
            passive[2].actors[7].max_hp - baseline[2].actors[7].max_hp, 1200
        )
        from wakfu_server.combat_effect_dispatch import EffectDispatcher

        execute = EffectDispatcher.execute
        observations = []

        def observe(dispatcher, invocation, **kwargs):
            result = execute(dispatcher, invocation, **kwargs)
            if invocation.reference in (344429, 344430):
                observations.append(
                    (
                        invocation.reference,
                        invocation.caster_id,
                        invocation.target_id,
                        result,
                    )
                )
            return result

        with patch.object(EffectDispatcher, "execute", observe):
            plain = self.next_owned_turn(passive)
        self.assertFalse(any(ref == 344430 for ref, *_ in observations), observations)
        observations.clear()
        entered = self.cast(passive, 6923, target=passive[2].actors[7].position)
        data = self.adopt(passive, entered.fight)
        before = data[2].actors[7].hp
        with patch.object(EffectDispatcher, "execute", observe):
            data = self.next_owned_turn(data)
        self.assertTrue(
            any(ref == 344430 and result for ref, _, _, result in observations),
            observations,
        )
        self.assertLess(data[2].actors[7].hp, before)

    def test_stasis_reservoir_reduces_actual_sp_cap_and_gains_controlled_stat(self):
        baseline = self.fixture()
        passive = self.fixture((6941,))
        self.assertEqual(
            passive[2].actors[7].effect_maxima[123],
            baseline[2].actors[7].effect_maxima[123] - 2,
        )
        self.assertEqual(
            passive[2].actors[7].effect_stats[87]
            - baseline[2].actors[7].effect_stats[87],
            50,
        )

    def test_regeneration_tradeoff_uses_actual_near_enemy_and_owner_level(self):
        # Native999 stop-after-success selects7678 near an enemy;7679 is
        # the ordered fallback, not a second simultaneous buff.
        for distance, state, deltas in (
            (3, 7678, {27: 50, 7: 600, 48: -10, 8: 0, 11: 0}),
            (5, 7679, {27: -50, 7: 0, 48: 0, 8: 600, 11: 1}),
        ):
            with self.subTest(distance=distance):
                baseline = self.fixture(target_distance=distance)
                passive = self.fixture((6927,), target_distance=distance)
                before = dict(passive[2].actors[7].effect_stats)
                baseline = self.next_owned_turn(baseline)
                passive = self.next_owned_turn(passive)
                entries = {
                    s.reference: s.level
                    for s in passive[2].actors[7].state_ledger.entries
                }
                self.assertEqual(entries.get(state), 200, entries)
                self.assertNotIn(7679 if state == 7678 else 7678, entries)
                actor = passive[2].actors[7]
                for stat, delta in deltas.items():
                    self.assertEqual(
                        actor.effect_stats[stat] - before[stat],
                        delta,
                        (distance, stat, entries),
                    )
                self.assertFalse(
                    {7678, 7679}
                    & {s.reference for s in baseline[2].actors[7].state_ledger.entries}
                )
