"""Initially wounded Agonia respects its native floors and earns the30-percent phase.

The wound amount is a declared pre-admission fixture premise. This does not
claim a full-health encounter or that the world spawns wounded bosses. Initial
states, paid hit, real start clocks, triggered6387, cells and births are native.
"""
import random
import struct
import unittest
from unittest.mock import patch


class AgoniaNativePhasePipelineTests(unittest.TestCase):
    def test_paid_hit_enters_thirty_band_and_real_start_produces_owned_crystals(self):
        from xelor_multiowner_fixture import TwoXelorFixture
        from wakfu_server.combat_actor import (
            actual_actor_stats,
            actual_monster_actor_stats,
        )
        from wakfu_server.combat_characteristic_percentage import (
            characteristic_percentage,
        )
        from wakfu_server.combat_effect_dispatch import EffectDispatcher
        from wakfu_server.combat_los import authoritative_visible
        from wakfu_server.combat_npc_spellbook import ordinary_npc_spellbook
        from wakfu_server.combat_obstacle_condition import footprint
        from wakfu_server.combat_qi_fight import current_registry
        from wakfu_server.combat_runtime_messages import RuntimeMessages
        from wakfu_server.combat_server_spell import (
            prepare_server_spell,
            prepare_server_turn_end,
            prepare_server_turn_start,
            server_runtime,
        )
        from wakfu_server.combat_spell_commit import commit_spell_transaction
        from wakfu_server.combat_summon_stats import registered_summon_stats
        from wakfu_server.fight_checkpoint_store import snapshot
        from tools.combat_audit_turns import advance_actual_turn

        fight, characters, monster, decks = TwoXelorFixture().fixture(
            caster_breed=8,
            second_player_breed=8,
            level=245,
            caster_aptitudes=((26, 40), (23, 22), (12, 62), (8, 1), (4, 1)),
            active_spells=(4777, 4780),
            second_player_spells=(4780,),
            native_target_ref=4664,
            native_target_level=203,
            native_target_initial_wounds=51750,
            enemy_position=(-6, -7, -1),
            second_player_position=(-8, -5, -1),
            third_player_position=(-9, -6, -1),
            compact_arena=False,
        )
        boss = fight.actors[-7]
        # The minimal shared fixture keeps only ref/id/map in its descriptor;
        # real NPC wire statistics additionally carry the native actor level.
        monster = dict(monster, level=boss.effective_level)
        # Original248368/877 clamps effective initial HP to phase-one70%.
        # Preserve that native guard; the declared wound premise cannot skip it.
        self.assertEqual(
            (boss.hp, boss.max_hp, boss.effect_stats[1]), (52500, 75000, 52500)
        )
        self.assertEqual(boss.effect_minima[1], 52500)
        self.assertEqual(characteristic_percentage(boss.hp, boss.max_hp), 70)
        self.assertEqual((boss.ap, boss.mp, boss.effect_stats[4]), (12, 6, 0))
        self.assertTrue(
            {5314, 5335, 5599}
            <= {state.reference for state in boss.state_ledger.entries}
        )
        self.assertNotIn(5317, {state.reference for state in boss.state_ledger.entries})
        book = ordinary_npc_spellbook(fight, boss, monster)
        self.assertEqual(set(book.levels), {6386, 6388, 6389})
        self.assertNotIn(6387, book.levels)
        self.assertEqual(fight.current.id, 7)
        current_registry(fight)
        trace = []
        original = EffectDispatcher.execute

        def observe(dispatcher, invocation, **kwargs):
            result = original(dispatcher, invocation, **kwargs)
            if invocation.reference in (248379, 248495, 248467, 248443, 248444, 248446):
                trace.append(
                    (
                        invocation.reference,
                        invocation.caster_id,
                        invocation.target_id,
                        result,
                    )
                )
            return result

        rng = random.Random(7)
        common = dict(player_characters=characters, deck_blobs=decks, rng=rng)
        runtime = RuntimeMessages(
            fight,
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
                **common,
            )[0],
        )

        def stats(actor, current):
            if getattr(actor, "native_summon_source", None) is not None:
                return registered_summon_stats(actor, current, 1134)
            values = dict(
                wp_current=actor.effect_stats[4],
                wp_maximum=actor.effect_maxima[4],
                fight=current,
            )
            if actor.id in characters:
                return actual_actor_stats(
                    characters[actor.id], actor, current.id, **values
                )
            return actual_monster_actor_stats(monster, actor, current.id, **values)

        paid_hits = []
        native_phases = []
        with patch.object(EffectDispatcher, "execute", observe):
            for _ in range(320):
                current = runtime.fight.current
                boss = runtime.fight.actors[-7]
                native_phases.append(
                    (
                        boss.hp,
                        boss.effect_minima[1],
                        tuple(
                            (entry.reference, entry.level)
                            for entry in boss.state_ledger.entries
                            if entry.reference == 5314
                        ),
                    )
                )
                crystals = [
                    actor
                    for actor in runtime.fight.actors.values()
                    if getattr(actor, "native_summon_source", None) is not None
                    and actor.native_summon_source.get("caster_id") == -7
                    and actor.native_summon_source.get("ref") == 4661
                ]
                if crystals:
                    break
                # Native phase-one own-start must lower the guard to30 before
                # ordinary paid injury can reach that next source-authored band.
                if (
                    current.id != 7
                    or boss.effect_minima[1] >= 52500
                    or boss.hp <= 22500
                    or current.ap < 2
                ):
                    advance_actual_turn(runtime)
                    continue
                self.assertEqual(boss.effect_minima[1], 22500)
                self.assertEqual(
                    next(
                        entry.level
                        for entry in boss.state_ledger.entries
                        if entry.reference == 5314
                    ),
                    2,
                )
                self.assertLess(
                    len(paid_hits),
                    64,
                    (
                        "Bounded paid producer budget exhausted",
                        paid_hits[-3:],
                        native_phases[-4:],
                    ),
                )
                reference = 4777 if current.ap >= 4 else 4780
                baseline = snapshot(runtime.fight)
                hp, ap = boss.hp, current.ap
                tx = prepare_server_spell(
                    struct.pack(">qqiih", 7, (7 << 32) | reference, *boss.position),
                    characters[7],
                    {-7: monster},
                    runtime.fight,
                    3,
                    decks[7],
                    action_id=runtime.action_id + 1,
                    line_of_sight=lambda origin, target, current: authoritative_visible(
                        1134,
                        origin,
                        target,
                        current,
                        blocking_footprints={
                            actor.id: footprint(actor.position, actor.physical_radius)
                            for actor in current.actors.values()
                            if actor.hp > 0
                        },
                    ),
                    critical=None,
                    **common,
                )
                self.assertEqual(snapshot(runtime.fight), baseline)
                self.assertGreater(tx.plan["costs"]["ap"], 0)
                self.assertEqual(tx.fight.actors[7].ap, ap - tx.plan["costs"]["ap"])
                self.assertLess(tx.fight.actors[-7].hp, hp)
                self.assertGreaterEqual(tx.fight.actors[-7].hp, 22500)
                self.assertEqual(tx.fight.actors[-7].max_hp, 75000)
                commit_spell_transaction(runtime, tx, stats_serializer=stats)
                paid_hits.append(
                    (hp, runtime.fight.actors[-7].hp, tx.plan["costs"]["ap"])
                )
                self.assertEqual(
                    runtime.fight.actors[-7].effect_stats[1],
                    runtime.fight.actors[-7].hp,
                )
            else:
                self.fail(
                    "Native Agonia did not produce crystals: "
                    + repr((paid_hits[-3:], native_phases[-4:], trace))
                )
        self.assertTrue(paid_hits)
        self.assertEqual(characteristic_percentage(paid_hits[-1][1], 75000), 30)
        current_registry(runtime.fight)
        boss = runtime.fight.actors[-7]
        self.assertEqual(
            next(
                entry.level
                for entry in boss.state_ledger.entries
                if entry.reference == 5314
            ),
            3,
        )
        self.assertEqual(boss.effect_minima[1], 0)  # Published native base minimum.
        self.assertFalse(
            any(
                row["manager_id"] == -7 and row["generic_effect"] in (248368, 248369)
                for row in runtime.fight.native_retained_records.values()
            )
        )
        successful = {reference for reference, _, _, result in trace if result}
        self.assertTrue(
            {248379, 248495, 248467, 248443, 248444, 248446} <= successful, trace
        )
        self.assertTrue(
            all(
                caster == -7
                for reference, caster, _, result in trace
                if result and reference in (248379, 248495, 248467, 248444)
            )
        )
        self.assertTrue(crystals)
        for crystal in crystals:
            self.assertGreater(crystal.hp, 0)
            self.assertIn(crystal.id, runtime.fight.native_summon_registrations)
