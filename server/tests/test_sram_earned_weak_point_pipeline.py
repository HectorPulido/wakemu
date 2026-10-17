"""Earn native Weak Point through paid rear attacks, then consume a real tier."""
import os
import random
import struct
import unittest


@unittest.skipUnless(
    os.environ.get("WAKFU_TEST_GRANTEDCAST") == "1", "native runtime opt-in"
)
class SramEarnedWeakPointPipelineTests(unittest.TestCase):
    def test_paid_rear_generators_cross_native_tier_then_finisher_consumes_it(self):
        from test_combat_spell_transaction import SpellTransactionTests
        from wakfu_server.combat_server_spell import (
            prepare_server_initialization,
            prepare_server_spell,
            prepare_server_turn_start,
            prepare_server_turn_end,
            server_runtime,
        )
        from wakfu_server.combat_runtime_messages import RuntimeMessages
        from wakfu_server.combat_movement_runtime import apply_client
        from wakfu_server.combat_ordinary_authority import native_facing
        from wakfu_server.combat_spell_commit import commit_spell_transaction
        from wakfu_server.combat_actor import (
            actual_actor_stats,
            actual_monster_actor_stats,
        )
        from wakfu_server.combat_los import authoritative_visible
        from wakfu_server.combat_reproduction_state import encode_state
        from wakfu_server.fight_checkpoint_store import snapshot
        from wakfu_server.spells import encode_deck
        from tools.combat_audit_turns import advance_actual_turn

        # Native NPC creation supplies HP/maxHP; never inflate an enemy to
        # preserve this sequence, refill AP or install a Weak Point threshold.
        character, monster, fight = SpellTransactionTests().native_server_fixture(
            4,
            200,
            full_health=True,
            native_qi=True,
            target_ref=4168,
            target_level=190,
            target_distance=2,
            variation_seed=17,
        )
        self.assertEqual(
            (monster["ref"], fight.actors[-7].effective_level), (4168, 190)
        )
        self.assertEqual((fight.actors[-7].hp, fight.actors[-7].max_hp), (8784, 8784))
        deck = encode_deck([4584, 4586])
        rng = random.Random(17)
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
        common = dict(rng=rng)
        runtime = RuntimeMessages(
            fight,
            turn_end_provider=lambda p, **kw: prepare_server_turn_end(
                character, {-7: monster}, p, deck, **common, **kw
            ),
            turn_start_provider=lambda p, **kw: prepare_server_turn_start(
                character, {-7: monster}, p, deck, area_callbacks=True, **common, **kw
            ),
            expiration_runtime_factory=lambda *, action_id: server_runtime(
                character,
                {-7: monster},
                deck,
                action_id=action_id,
                critical=False,
                **common,
            )[0],
        )

        def weak_point():
            return sum(
                row.level
                for row in runtime.fight.actors[7].state_ledger.entries
                if row.reference == 3114
            )

        def stats(actor, state=None):
            state = runtime.fight if state is None else state
            if actor.id == 7:
                return actual_actor_stats(
                    character,
                    actor,
                    state.id,
                    wp_current=actor.effect_stats[4],
                    wp_maximum=6,
                    fight=state,
                )
            return actual_monster_actor_stats(
                dict(monster, level=actor.effective_level),
                actor,
                state.id,
                wp_current=0,
                wp_maximum=0,
                fight=state,
            )

        def los(origin, target, current):
            return authoritative_visible(
                character["map_id"],
                origin,
                target,
                current,
                blocking_footprints={
                    actor.id: {actor.position[:2]}
                    for actor in current.actors.values()
                    if actor.hp > 0
                },
            )

        def cast(spell):
            original = snapshot(runtime.fight)
            tx = prepare_server_spell(
                struct.pack(
                    ">qqiih", 7, (7 << 32) | spell, *runtime.fight.actors[-7].position
                ),
                character,
                {-7: monster},
                runtime.fight,
                3,
                deck,
                action_id=runtime.action_id + 1,
                line_of_sight=los,
                critical=False,
                rng=rng,
            )
            self.assertEqual(snapshot(runtime.fight), original)
            packets = commit_spell_transaction(runtime, tx, stats_serializer=stats)
            self.assertTrue(packets)
            self.assertTrue(any(tx.outcomes))
            return tx

        def next_personal_turn():
            for _ in range(8):
                advance_actual_turn(runtime)
                if runtime.fight.current.id == 7:
                    return
            self.fail("Sram did not reach its next actual personal turn")

        self.assertEqual(weak_point(), 50)  # Native7556 ->410036 ->410325.
        self.assertNotEqual(native_facing(fight.actors[7], fight.actors[-7]), "BACK")
        movement, _ = apply_client(
            runtime,
            3,
            struct.pack(">q", 7)
            + b"".join(
                struct.pack(">iih", *cell)
                for cell in ((-8, -8, -1), (-7, -8, -1), (-6, -8, -1))
            ),
            lambda actor: stats(actor),
            runtime_stats_serializer=stats,
        )
        self.assertTrue(movement)
        self.assertEqual(runtime.fight.actors[7].position, (-6, -8, -1))
        self.assertEqual(
            native_facing(runtime.fight.actors[7], runtime.fight.actors[-7]), "BACK"
        )
        earned = 0
        for _ in range(4):
            before = weak_point()
            ap = runtime.fight.actors[7].ap
            hp = runtime.fight.actors[-7].hp
            generated = cast(4584)
            # Native159114 +159115: +10 ordinary, +5 actual backstab.
            self.assertEqual(weak_point(), before + 15)
            self.assertEqual(generated.plan["costs"]["ap"], 2)
            self.assertEqual(runtime.fight.actors[7].ap, ap - 2)
            self.assertLess(runtime.fight.actors[-7].hp, hp)
            self.assertGreater(runtime.fight.actors[-7].hp, 0)
            earned += 15
            next_personal_turn()
        self.assertEqual(earned, 60)
        self.assertGreaterEqual(weak_point(), 100)
        self.assertLess(weak_point(), 150)
        before = weak_point()
        hp = runtime.fight.actors[-7].hp
        ap = runtime.fight.actors[7].ap
        max_ap = runtime.fight.actors[7].max_ap
        mp = runtime.fight.actors[7].mp
        max_mp = runtime.fight.actors[7].max_mp
        wp = runtime.fight.actors[7].effect_stats[4]
        finisher = cast(4586)
        # Native413439 is level100..149; child413442 consumes100,
        # not the obsolete 2024 guide's75-point Trauma threshold.
        self.assertEqual(weak_point(), before - 100)
        self.assertEqual(finisher.plan["costs"]["ap"], 6)
        # Tier100 also grants native +2 maximum/current AP/MP for one
        # target turn (413457/413458, flag17) and +2 current WP (413459).
        self.assertEqual(runtime.fight.actors[7].ap, ap - 6 + 2)
        self.assertEqual(runtime.fight.actors[7].max_ap, max_ap + 2)
        self.assertEqual(runtime.fight.actors[7].mp, mp + 2)
        self.assertEqual(runtime.fight.actors[7].max_mp, max_mp + 2)
        self.assertEqual(runtime.fight.actors[7].effect_stats[4], min(6, wp + 2))
        self.assertLess(runtime.fight.actors[-7].hp, hp)
        self.assertGreater(runtime.fight.actors[-7].hp, 0)
        rejected_before = encode_state(runtime)
        with self.assertRaisesRegex(
            ValueError, "Insufficient authoritative spell resources"
        ):
            cast(4586)
        self.assertEqual(encode_state(runtime), rejected_before)
