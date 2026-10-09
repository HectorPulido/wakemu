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
        ) = fixture_module.SpellTransactionTests().native_server_fixture(
            11, 20, native_qi=True
        )
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
        # Berserker 3702 -> eYg353687 -> eYm353665 scales the nested
        # Vitality state3231 to actor level * 400%; eWN20 applies that
        # level to both current and maximum HP.
        self.assertEqual((actor.hp, actor.max_hp), (140, 330))
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
        # Native eYs refs 416623/418364 select the missing/current HP
        # percentages (57/42) from the post-innate 140/330 snapshot. Ref416651
        # maps its level57 through 0.0025 growth to child level47; 416652 then
        # applies exactly47 armor.
        self.assertEqual(after.effect_stats[97], 47)
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

    def test_granted_state_cast_commits_resources_and_consumption_as_one_preview(self):
        from wakfu_server.combat_runtime_messages import RuntimeMessages
        from wakfu_server.combat_spell_commit import commit_spell_transaction

        (
            character,
            monster,
            fight,
        ) = fixture_module.SpellTransactionTests().native_server_fixture(
            11, 200, native_qi=True
        )
        deck = encode_deck([], [])
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
        self.assertTrue({6065, 8586} <= set(granted_spells(started, 7)))
        before_cast = snapshot(started)
        caster_before = started.actors[7]
        resources_before = (
            caster_before.ap,
            caster_before.mp,
            caster_before.effect_stats[4],
        )
        body = struct.pack(">qqiih", 7, 6065, *caster_before.position)
        transaction = prepare_server_spell(
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
        self.assertTrue(transaction.outcomes[0])
        self.assertEqual(
            transaction.plan["costs"],
            {"ap": 1, "mp": 0, "wp": 1, "conditional_rules": 0},
        )
        prepared = transaction.fight.actors[7]
        self.assertEqual(
            (prepared.ap, prepared.mp, prepared.effect_stats[4]),
            tuple(
                value - transaction.plan["costs"][key]
                for value, key in zip(resources_before, ("ap", "mp", "wp"))
            ),
        )
        self.assertNotIn(
            9312, {state.reference for state in prepared.state_ledger.entries}
        )
        self.assertNotIn(
            9314, {state.reference for state in prepared.state_ledger.entries}
        )
        self.assertEqual(snapshot(started), before_cast)

        runtime = RuntimeMessages(started)
        runtime.action_id = 1  # The already adopted fight-start initialization.
        packets = commit_spell_transaction(
            runtime,
            transaction,
            stats_serializer=lambda _actor, _fight: b"native-stats",
        )
        self.assertTrue(packets)
        self.assertIs(runtime.fight, transaction.fight)
        self.assertEqual(runtime.action_id, 2)
        committed = runtime.fight.actors[7]
        self.assertEqual(
            (committed.ap, committed.mp, committed.effect_stats[4]),
            (prepared.ap, prepared.mp, prepared.effect_stats[4]),
        )
        self.assertNotIn(
            9312, {state.reference for state in committed.state_ledger.entries}
        )
        self.assertNotIn(
            9314, {state.reference for state in committed.state_ledger.entries}
        )
        self.assertEqual(snapshot(started), before_cast)

        # 8586 is another state-granted Sacrier action. Resolve and prepare it
        # from the committed transition's real grant book, not the player deck
        # or the earlier pre-transition snapshot.
        from wakfu_server.combat_cast import resolve_owned_spell_action

        committed_snapshot = snapshot(runtime.fight)
        actor, reference, level = resolve_owned_spell_action(
            {"actor_id": 7, "spell_uid": 8586}, character, runtime.fight, 3, deck
        )
        self.assertIs(actor, runtime.fight.actors[7])
        self.assertEqual((reference, level), (8586, 200))
        dependent = prepare_server_spell(
            struct.pack(">qqiih", 7, 8586, *runtime.fight.actors[7].position),
            character,
            {-7: monster},
            runtime.fight,
            3,
            deck,
            action_id=3,
            line_of_sight=lambda *args: True,
            critical=False,
            rng=rng,
        )
        self.assertEqual(dependent.plan["spell_id"], 8586)
        self.assertEqual(dependent.plan["evaluation_level"], 200)
        self.assertEqual(snapshot(runtime.fight), committed_snapshot)

        adopted_snapshot = snapshot(runtime.fight)
        rng_after_commit = rng.getstate()
        with self.assertRaisesRegex(ValueError, "turn|limit"):
            prepare_server_spell(
                body,
                character,
                {-7: monster},
                runtime.fight,
                3,
                deck,
                action_id=3,
                line_of_sight=lambda *args: True,
                critical=False,
                rng=rng,
            )
        self.assertEqual(snapshot(runtime.fight), adopted_snapshot)
        self.assertEqual(rng.getstate(), rng_after_commit)

    def test_stored_damage_is_created_by_real_blood_cast_then_healed_and_consumed(self):
        (
            character,
            monster,
            fight,
        ) = fixture_module.SpellTransactionTests().native_server_fixture(
            11, 20, native_qi=True
        )
        from wakfu_server.combat_qi_fight import move_registered_actor

        target = fight.actors[-7]
        self.assertIn((-7, -7, -1), fight.walkable)
        move_registered_actor(fight, target, (-7, -7, -1))
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
            struct.pack(">qqiih", 7, (7 << 32) + 5028, *target.position),
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
        # Stored state4840 enters eYs ref416720 at level5. Its native
        # max-HP formula floors 330 * 0.01 * 5 to child level16; eXt ref416719
        # applies that amount to the caster (140→124).
        self.assertEqual(injured.hp, 124)
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
        # This retained-state heal is class25 ref416656. Its far parameter
        # uses the authoritative maximum-HP context and native percent
        # rounding; keep the expected value tied to the resolved HP snapshot.
        # Native ref416656 raw pairs [0,1,0,0,1,0] evaluate to
        # [stored level5, mastery mask0, far1]: 5% of maximum330,
        # rounded to16 before eXs applies the heal to actual HP124.
        self.assertEqual(healed.hp - injured.hp, 16)
        self.assertEqual(healed.hp, 140)
        self.assertGreater(healed.effect_stats[97], 0)
        self.assertNotIn(4840, {s.reference for s in healed.state_ledger.entries})
        self.assertNotIn(9312, {s.reference for s in healed.state_ledger.entries})
        self.assertEqual(snapshot(blood.fight), before)
        self.assertTrue(tx.outcomes[0])
