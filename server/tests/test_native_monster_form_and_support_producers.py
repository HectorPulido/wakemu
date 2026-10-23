"""Real owned NPC support after paid hostile damage to a genuine native ally."""
from random import Random
import struct
import unittest
from unittest.mock import patch


class NativeMonsterFormAndSupportProducerTests(unittest.TestCase):
    def _scene(
        self,
        reference,
        native_level,
        *,
        primary_position=(-6, -7, -1),
        injured_position=(-7, -7, -1)
    ):
        from xelor_multiowner_fixture import TwoXelorFixture
        from wakfu_server.combat_runtime_messages import RuntimeMessages
        from wakfu_server.combat_server_spell import (
            prepare_server_turn_start,
            prepare_server_turn_end,
            server_runtime,
        )

        fixture = TwoXelorFixture()
        fight, characters, monster, decks = fixture.fixture(
            caster_breed=8,
            second_player_breed=8,
            level=14,
            active_spells=(4780,),
            compact_arena=False,
            enemy_position=primary_position,
            second_player_position=(-10, -7, -1),
            third_player_position=(-10, -6, -1),
            native_target_ref=reference,
            native_target_level=native_level,
            extra_native_targets=(
                (-8, 41, 14, injured_position),
                (-9, 2616, 6, (-6, -6, -1)),
            ),
        )
        monsters = fixture.native_monsters
        rng = Random(7)
        common = dict(player_characters=characters, deck_blobs=decks, rng=rng)
        runtime = RuntimeMessages(
            fight,
            turn_end_provider=lambda p, **kw: prepare_server_turn_end(
                characters[7], monsters, p, decks[7], **common, **kw
            ),
            turn_start_provider=lambda p, **kw: prepare_server_turn_start(
                characters[7], monsters, p, decks[7], **common, **kw
            ),
            expiration_runtime_factory=lambda *, action_id: server_runtime(
                characters[7],
                monsters,
                decks[7],
                action_id=action_id,
                critical=False,
                **common,
            )[0],
        )
        return runtime, characters, monsters, decks, rng

    def _cast(self, scene, spell, target_id, *, rollback=False):
        from wakfu_server.combat_server_spell import prepare_server_spell
        from wakfu_server.combat_npc_spell import prepare_npc_spell, owned_spells
        from wakfu_server.combat_spell_commit import commit_spell_transaction
        from wakfu_server.combat_geometry_snapshot import source_snapshot
        from wakfu_server.combat_actor import (
            actual_actor_stats,
            actual_monster_actor_stats,
        )

        runtime, characters, monsters, decks, rng = scene
        fight, actor = runtime.fight, runtime.fight.current
        cell = (
            fight.actors[target_id].position
            if target_id is not None
            else actor.position
        )
        common = dict(
            action_id=runtime.action_id + 1,
            rng=rng,
            player_characters=characters,
            deck_blobs=decks,
        )
        if actor.controlled:
            from wakfu_server.combat_los import authoritative_visible
            from wakfu_server.combat_obstacle_condition import footprint

            def los(origin, destination, current):
                return authoritative_visible(
                    1134,
                    origin,
                    destination,
                    current,
                    blocking_footprints={
                        a.id: footprint(a.position, a.physical_radius)
                        for a in current.actors.values()
                        if a.hp > 0
                    },
                )

            transaction = prepare_server_spell(
                struct.pack(">qqiih", actor.id, (actor.id << 32) | spell, *cell),
                characters[actor.id],
                monsters,
                fight,
                actor.owner_id,
                decks[actor.id],
                critical=False,
                line_of_sight=los,
                **common,
            )
        else:
            book = owned_spells(fight, monsters, player_characters=characters)
            self.assertIn(spell, book)
            transaction = prepare_npc_spell(
                fight,
                dict(
                    type="cast",
                    spellId=spell,
                    level=book[spell],
                    targetId=target_id,
                    target=list(cell),
                ),
                characters[7],
                monsters,
                decks[7],
                **common,
            )
        self.assertGreater(
            sum(transaction.plan["costs"][key] for key in ("ap", "mp", "wp")), 0
        )
        if rollback:
            before = source_snapshot(runtime.fight)
            with self.assertRaisesRegex(ValueError, "support serializer rollback"):
                commit_spell_transaction(
                    runtime,
                    transaction,
                    stats_serializer=lambda *args: (_ for _ in ()).throw(
                        ValueError("support serializer rollback")
                    ),
                )
            self.assertEqual(source_snapshot(runtime.fight), before)

        def stats(current, preview):
            values = dict(
                wp_current=current.effect_stats[4],
                wp_maximum=current.effect_maxima[4],
                fight=preview,
            )
            if current.controlled:
                return actual_actor_stats(
                    characters[current.id], current, preview.id, **values
                )
            return actual_monster_actor_stats(
                monsters[current.id], current, preview.id, **values
            )

        before_ap = actor.ap
        packets = commit_spell_transaction(runtime, transaction, stats_serializer=stats)
        self.assertEqual(
            runtime.fight.actors[actor.id].ap,
            before_ap - transaction.plan["costs"]["ap"],
        )
        return transaction, packets

    def _turn(self, scene, identity):
        from tools.combat_audit_turns import advance_actual_turn

        runtime = scene[0]
        for _ in range(2 * len(runtime.fight.actors)):
            if runtime.fight.current.id == identity:
                return
            advance_actual_turn(runtime)
        self.fail("Native support owner did not receive its real turn")

    def test_white_miaumiau_real_paid_injury_then_owned_ally_only_heal_and_rollback(
        self,
    ):
        from wakfu_server.combat_healing_handler import NativeHealingHandler

        scene = self._scene(2617, 6)
        runtime = scene[0]
        self.assertEqual(runtime.fight.current.id, 7)
        initial = {
            identity: actor.hp for identity, actor in runtime.fight.actors.items()
        }
        self.assertEqual(runtime.fight.actors[-8].team, runtime.fight.actors[-7].team)
        self.assertFalse(runtime.fight.actors[-8].controlled)
        self._cast(scene, 4780, -8)
        injured = runtime.fight.actors[-8].hp
        self.assertGreater(injured, 0)
        self.assertLess(injured, initial[-8])
        self._turn(scene, -7)
        before = {
            identity: actor.hp for identity, actor in runtime.fight.actors.items()
        }
        calls = []
        original = NativeHealingHandler.__call__

        def observe(handler, effect, values, invocation):
            result = original(handler, effect, values, invocation)
            calls.append(
                (
                    invocation.reference,
                    invocation.caster_id,
                    invocation.target_id,
                    result,
                )
            )
            return result

        with patch.object(NativeHealingHandler, "__call__", observe):
            transaction, packets = self._cast(scene, 2794, -7, rollback=True)
        self.assertTrue(
            any(target == -8 and result for _, _, target, result in calls), calls
        )
        self.assertTrue(
            all(caster == -7 and target in (-8, -9) for _, caster, target, _ in calls),
            calls,
        )
        self.assertGreater(runtime.fight.actors[-8].hp, before[-8])
        self.assertLessEqual(runtime.fight.actors[-8].hp, initial[-8])
        self.assertEqual(runtime.fight.actors[-9].hp, initial[-9])
        for identity in (7, 8, 9, -7):
            self.assertEqual(runtime.fight.actors[identity].hp, before[identity])
        self.assertTrue(any(opcode == 12613 for opcode, _ in packets))
        self.assertTrue(transaction.outcomes)

    def test_wild_jalalinea_paid_attack_and_injured_ally_heal_preserve_form_wp_guards(
        self,
    ):
        from wakfu_server.combat_npc_spell import owned_spells, prepare_npc_spell
        from wakfu_server.combat_geometry_snapshot import source_snapshot

        scene = self._scene(
            41, 14, primary_position=(-9, -7, -1), injured_position=(-9, -6, -1)
        )
        runtime = scene[0]
        healthy = runtime.fight.actors[-8].hp
        self._cast(scene, 4780, -8)
        injured = runtime.fight.actors[-8].hp
        self.assertTrue(0 < injured < healthy)
        self._turn(scene, -7)
        runtime, characters, monsters, decks, rng = scene
        actor = runtime.fight.actors[-7]
        self.assertGreaterEqual(actor.ap, 6)
        self.assertEqual((actor.effect_stats[4], actor.effect_maxima[4]), (0, 0))
        states = {entry.reference for entry in actor.state_ledger.entries}
        self.assertIn(4402, states)
        self.assertNotIn(7134, states)
        book = owned_spells(runtime.fight, monsters, player_characters=characters)
        self.assertTrue({5771, 7362, 7363, 7364} <= set(book))
        before = source_snapshot(runtime.fight)
        for spell in (7362, 7363, 7364):
            with self.subTest(spell=spell):
                with self.assertRaisesRegex(
                    ValueError, "Insufficient authoritative spell resources"
                ) as rejected:
                    prepare_npc_spell(
                        runtime.fight,
                        dict(
                            type="cast",
                            spellId=spell,
                            level=book[spell],
                            targetId=-8,
                            target=list(runtime.fight.actors[-8].position),
                        ),
                        characters[7],
                        monsters,
                        decks[7],
                        action_id=runtime.action_id + 1,
                        rng=rng,
                        player_characters=characters,
                        deck_blobs=decks,
                    )
                self.assertEqual(
                    rejected.exception.cast_validation_code, "insufficient_resources"
                )
                self.assertIn(
                    "wp", rejected.exception.native_resource_diagnostic["deficits"]
                )
                self.assertEqual(source_snapshot(runtime.fight), before)
        pc_before = runtime.fight.actors[7].hp
        transaction, packets = self._cast(scene, 5770, 7, rollback=True)
        self.assertLess(runtime.fight.actors[7].hp, pc_before)
        self.assertGreater(runtime.fight.actors[7].hp, 0)
        self.assertTrue(transaction.outcomes)
        self.assertTrue(any(opcode == 12613 for opcode, _ in packets))
        from tools.combat_audit_turns import advance_actual_turn

        # Preserve the actual5770 payment, then earn the next full native AP
        # turn through the ordinary end/ACK boundary before paying5771.
        advance_actual_turn(runtime)
        self._turn(scene, -7)
        before_heal = runtime.fight.actors[-8].hp
        transaction, packets = self._cast(scene, 5771, -8, rollback=True)
        self.assertGreater(runtime.fight.actors[-8].hp, before_heal)
        self.assertLessEqual(runtime.fight.actors[-8].hp, healthy)
        self.assertEqual(runtime.fight.actors[-7].effect_stats[4], 0)
        self.assertTrue(transaction.outcomes)
        self.assertTrue(any(opcode == 12613 for opcode, _ in packets))

    def test_wild_tofu_native_wp_zero_preserves_form_affordability(self):
        from wakfu_server.combat_npc_spell import owned_spells, prepare_npc_spell
        from wakfu_server.combat_geometry_snapshot import source_snapshot

        scene = self._scene(4, 12, primary_position=(-9, -7, -1))
        self._turn(scene, -7)
        runtime, characters, monsters, decks, rng = scene
        actor = runtime.fight.actors[-7]
        self.assertEqual((actor.effect_stats[4], actor.effect_maxima[4]), (0, 0))
        book = owned_spells(runtime.fight, monsters, player_characters=characters)
        before = source_snapshot(runtime.fight)
        for spell in (7359, 7360, 7361):
            with self.subTest(spell=spell):
                self.assertIn(spell, book)
                with self.assertRaisesRegex(
                    ValueError, "Insufficient authoritative spell resources"
                ) as rejected:
                    prepare_npc_spell(
                        runtime.fight,
                        dict(
                            type="cast",
                            spellId=spell,
                            level=book[spell],
                            targetId=-8,
                            target=list(runtime.fight.actors[-8].position),
                        ),
                        characters[7],
                        monsters,
                        decks[7],
                        action_id=runtime.action_id + 1,
                        rng=rng,
                        player_characters=characters,
                        deck_blobs=decks,
                    )
                self.assertIn(
                    "wp", rejected.exception.native_resource_diagnostic["deficits"]
                )
                self.assertEqual(source_snapshot(runtime.fight), before)


if __name__ == "__main__":
    unittest.main()
