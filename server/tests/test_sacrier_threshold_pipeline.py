"""Native Sacrier HP boundaries exercised through real owned spell previews."""
import random
import struct
import unittest

import test_combat_spell_transaction as fixture_module
from wakfu_server.combat_hp_raw import set_hp_raw_current
from wakfu_server.combat_qi_fight import move_registered_actor
from wakfu_server.combat_server_spell import (
    prepare_server_initialization,
    prepare_server_spell,
    prepare_server_turn_start,
)
from wakfu_server.fight_checkpoint_store import snapshot
from wakfu_server.spells import encode_deck


class SacrierThresholdPipelineTests(unittest.TestCase):
    def initialized(self, passives=()):
        (
            character,
            monster,
            fight,
        ) = fixture_module.SpellTransactionTests().native_server_fixture(
            11, 200, native_qi=True, target_hp=20000
        )
        move_registered_actor(fight, fight.actors[-7], (-7, -7, -1))
        # Start at full health so the native below-50% subscription has not
        # already installed its once-only marker before the boundary probe.
        set_hp_raw_current(fight.actors[7], fight.actors[7].max_hp)
        deck = encode_deck([5028, 5032], list(passives))
        rng = random.Random(7)
        initialized, _ = prepare_server_initialization(
            character,
            {-7: monster},
            fight,
            3,
            deck,
            action_id=1,
            rng=rng,
            fight_start=True,
        )
        return character, monster, initialized, deck, rng

    def cast(self, fixture, reference, *, action_id=2, self_target=False):
        character, monster, fight, deck, rng = fixture
        target = fight.actors[7 if self_target else -7]
        uid = reference if reference == 6065 else (7 << 32) | reference
        before = snapshot(fight)
        transaction = prepare_server_spell(
            struct.pack(">qqiih", 7, uid, *target.position),
            character,
            {-7: monster},
            fight,
            3,
            deck,
            action_id=action_id,
            line_of_sight=lambda *args: True,
            critical=False,
            rng=rng,
        )
        self.assertEqual(snapshot(fight), before)
        self.assertTrue(transaction.outcomes[0])
        return transaction

    @staticmethod
    def states(actor):
        return {state.reference for state in actor.state_ledger.entries}

    def test_refusal_crossing_twenty_percent_includes_equal_start_not_equal_end(self):
        # 5028's native state7903 level5 subtracts floor(maxHP*5%).
        # Refusal353207 tests the pre-loss HP;316715 tests post-loss HP.
        for passives in ((), (5052,)):
            for relative in (-1, 0, 1):
                with self.subTest(passives=passives, relative=relative):
                    fixture = self.initialized(passives)
                    actor = fixture[2].actors[7]
                    threshold = actor.max_hp // 5
                    loss = actor.max_hp * 5 // 100
                    start = threshold + loss + relative
                    set_hp_raw_current(actor, start)
                    result = self.cast(fixture, 5028)
                    after = result.fight.actors[7]
                    self.assertEqual(after.hp, threshold + relative)
                    activates = passives == (5052,) and relative == -1
                    self.assertEqual(3633 in self.states(after), activates)
                    self.assertEqual(
                        after.effect_stats[97], threshold if activates else 0
                    )
                    self.assertEqual(actor.hp, start)

    def test_refusal_does_not_activate_when_already_below_twenty_percent(self):
        fixture = self.initialized((5052,))
        actor = fixture[2].actors[7]
        set_hp_raw_current(actor, actor.max_hp // 5 - 1)
        after = self.cast(fixture, 5028).fight.actors[7]
        self.assertNotIn(3633, self.states(after))
        self.assertEqual(after.effect_stats[97], 0)

    def test_refusal_real_granted_heal_uses_native_threshold_plus_one(self):
        fixture = self.initialized((5052,))
        actor = fixture[2].actors[7]
        threshold = actor.max_hp // 5
        set_hp_raw_current(actor, threshold + actor.max_hp * 5 // 100 - 1)
        blood = self.cast(fixture, 5028)
        self.assertIn(3633, self.states(blood.fight.actors[7]))
        chained = (*fixture[:2], blood.fight, *fixture[3:])
        healed = self.cast(chained, 6065, action_id=3, self_target=True).fight.actors[7]
        # Refusal353211 ->353212/353213 ->353214 changes the actual live
        # heal runner to 1 + floor(maxHP*.20) - currentHP, rather than the
        # original stored5%. The native constant1 deliberately ends at20%+1.
        self.assertEqual(healed.hp, threshold + 1)
        self.assertNotIn(4840, self.states(healed))

    def test_native_turn_start_fifty_percent_marker_is_strict(self):
        for relative in (-1, 0, 1):
            with self.subTest(relative=relative):
                character, monster, fight, deck, rng = self.initialized()
                actor = fight.actors[7]
                self.assertNotIn(9315, self.states(actor))
                set_hp_raw_current(actor, actor.max_hp // 2 + relative)
                before = snapshot(fight)
                result, _ = prepare_server_turn_start(
                    character,
                    {-7: monster},
                    fight,
                    deck,
                    actor_id=7,
                    action_id=2,
                    rng=rng,
                )
                self.assertEqual(snapshot(fight), before)
                self.assertEqual(9315 in self.states(result.actors[7]), relative == -1)

    def test_punishment_self_loss_floor_and_hp_scaled_damage_with_passives(self):
        # Current native level200 metadata and real eYr state-level branch.
        # eYs float32 percentage evaluation yields854, not a Python-rounded855.
        expected = {20: (1, 413, 100), 50: (571, 347, 80), 100: (1996, 205, 30)}
        for passives in ((), (5052,), (7216,)):
            for percent, (hp, damage, stored) in expected.items():
                with self.subTest(passives=passives, percent=percent):
                    fixture = self.initialized(passives)
                    actor = fixture[2].actors[7]
                    set_hp_raw_current(actor, actor.max_hp * percent // 100)
                    enemy_hp = fixture[2].actors[-7].hp
                    transaction = self.cast(fixture, 5032)
                    after = transaction.fight.actors[7]
                    self.assertEqual(after.hp, hp)
                    self.assertEqual(enemy_hp - transaction.fight.actors[-7].hp, damage)
                    entry = next(
                        s for s in after.state_ledger.entries if s.reference == 4840
                    )
                    self.assertEqual(entry.level, stored)
                    self.assertEqual(
                        3633 in self.states(after),
                        passives == (5052,) and percent == 20,
                    )
                    self.assertEqual(
                        after.effect_stats[97],
                        570 if passives == (5052,) and percent == 20 else 0,
                    )
                    self.assertGreater(after.hp, 0)

    def test_self_loss_bypasses_refusal_armor_without_duplicate_threshold_state(self):
        fixture = self.initialized((5052,))
        actor = fixture[2].actors[7]
        threshold = actor.max_hp // 5
        loss = actor.max_hp * 5 // 100
        set_hp_raw_current(actor, threshold + loss - 1)
        first = self.cast(fixture, 5028)
        chained = (*fixture[:2], first.fight, *fixture[3:])
        second = self.cast(chained, 5028, action_id=3)
        before, after = first.fight.actors[7], second.fight.actors[7]
        self.assertEqual(before.hp - after.hp, loss)
        self.assertEqual(before.effect_stats[97], threshold)
        self.assertEqual(after.effect_stats[97], threshold)
        self.assertEqual(
            sum(s.reference == 3633 for s in after.state_ledger.entries), 1
        )
