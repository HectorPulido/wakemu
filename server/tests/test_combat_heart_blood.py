"""6065 is obtained from the native Sacrier innate, never inserted in deck."""
import random
import struct
import unittest
from unittest.mock import patch
import test_combat_spell_transaction as fixture_module
from wakfu_server.combat_server_spell import (
    prepare_server_initialization,
    prepare_server_spell,
)
from wakfu_server.combat_spell_grant import granted_spells
from wakfu_server.spells import encode_deck
from wakfu_server.fight_checkpoint_store import snapshot


@patch.dict("os.environ", {"WAKFU_NATIVE_GRANTED_CAST": "1"})
class NativeHeartBloodTests(unittest.TestCase):
    def test_innate_grant_self_cast_armor_consumption_and_turn_limit(self):
        (
            character,
            monster,
            fight,
        ) = fixture_module.SpellTransactionTests().native_server_fixture(11, 20)
        deck = encode_deck([], [])
        rng = random.Random(7)
        original = snapshot(fight)
        started, _ = prepare_server_initialization(
            character,
            {-7: monster},
            fight,
            3,
            deck,
            action_id=1,
            rng=rng,
            fight_start=True,
        )
        self.assertEqual(snapshot(fight), original)
        self.assertEqual(granted_spells(started, 7)[6065]["level"], 20)
        actor = started.actors[7]
        self.assertEqual((actor.hp, actor.max_hp), (60, 250))
        self.assertIn(9312, {s.reference for s in actor.state_ledger.entries})
        before = snapshot(started)
        body = struct.pack(">qqiih", 7, 6065, *actor.position)
        tx = prepare_server_spell(
            body,
            character,
            {-7: monster},
            started,
            3,
            deck,
            action_id=2,
            line_of_sight=lambda *args: True,
            critical=False,
            rng=rng,
        )
        after = tx.fight.actors[7]
        self.assertTrue(tx.outcomes[0])
        self.assertEqual(
            tx.plan["costs"], {"ap": 1, "mp": 0, "wp": 1, "conditional_rules": 0}
        )
        self.assertEqual((after.ap, after.effect_stats[4]), (5, 5))
        self.assertEqual(after.effect_stats[97], 48)
        self.assertNotIn(9312, {s.reference for s in after.state_ledger.entries})
        self.assertNotIn(9314, {s.reference for s in after.state_ledger.entries})
        self.assertEqual(snapshot(started), before)
        stable = snapshot(tx.fight)
        random_before = rng.getstate()
        with self.assertRaisesRegex(ValueError, "turn|limit"):
            prepare_server_spell(
                body,
                character,
                {-7: monster},
                tx.fight,
                3,
                deck,
                action_id=3,
                line_of_sight=lambda *args: True,
                critical=False,
                rng=rng,
            )
        self.assertEqual(snapshot(tx.fight), stable)
        self.assertEqual(rng.getstate(), random_before)

    def test_stored_damage_is_created_by_real_blood_cast_then_healed_and_consumed(self):
        (
            character,
            monster,
            fight,
        ) = fixture_module.SpellTransactionTests().native_server_fixture(11, 20)
        fight.actors[-7].position = (1, 0, 0)
        deck = encode_deck([5028], [])
        rng = random.Random(7)
        started, _ = prepare_server_initialization(
            character,
            {-7: monster},
            fight,
            3,
            deck,
            action_id=1,
            rng=rng,
            fight_start=True,
        )
        blood = prepare_server_spell(
            struct.pack(">qqiih", 7, (7 << 32) + 5028, 1, 0, 0),
            character,
            {-7: monster},
            started,
            3,
            deck,
            action_id=2,
            line_of_sight=lambda *args: True,
            critical=False,
            rng=rng,
        )
        injured = blood.fight.actors[7]
        self.assertEqual(injured.hp, 48)
        stored = next(s for s in injured.state_ledger.entries if s.reference == 4840)
        self.assertEqual(stored.level, 5)
        before = snapshot(blood.fight)
        tx = prepare_server_spell(
            struct.pack(">qqiih", 7, 6065, *injured.position),
            character,
            {-7: monster},
            blood.fight,
            3,
            deck,
            action_id=3,
            line_of_sight=lambda *args: True,
            critical=False,
            rng=rng,
        )
        healed = tx.fight.actors[7]
        # Native heal25 param1 is percent: stored level5 × maxHP250 /100
        # is truncated to12, restoring HP48→60; it is not5flatHP.
        self.assertEqual(healed.hp, 60)
        self.assertGreater(healed.effect_stats[97], 0)
        self.assertNotIn(4840, {s.reference for s in healed.state_ledger.entries})
        self.assertNotIn(9312, {s.reference for s in healed.state_ledger.entries})
        self.assertEqual(snapshot(blood.fight), before)
        self.assertTrue(tx.outcomes[0])
