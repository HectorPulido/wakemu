"""Actual Sacrifice cast, incoming owned spell and deferred swap pipeline."""
import random
import struct
import unittest


class SacrificePipelineTests(unittest.TestCase):
    def fixture(self, *, extra_active=(), native_scenario=False):
        from test_combat_spell_transaction import SpellTransactionTests
        from wakfu_server.combat_state import Actor, Fight
        from wakfu_server.combat_actor_snapshot import build_player_snapshot
        from wakfu_server.combat_hp_raw import set_hp_raw_current
        from wakfu_server.combat_terrain import local_arena
        from wakfu_server.combat_geometry_snapshot import freeze_terrain
        from wakfu_server.combat_global_pv_collections import (
            initialize_global_pv_collections,
        )
        from wakfu_server.combat_qi_fight import (
            prepare_fresh_actor_slots,
            install_fresh_actor_slots,
        )
        from wakfu_server.spells import encode_deck

        source = SpellTransactionTests()
        native_options = (
            dict(full_health=True, target_ref=4168, target_level=190)
            if native_scenario
            else {}
        )
        character, creature, original = source.native_server_fixture(
            11, 200, native_qi=True, **native_options
        )
        attacker_character, _, _ = source.native_server_fixture(
            15, 200, full_health=native_scenario
        )
        attacker_character = dict(attacker_character, id=8, account_id=4)
        protector, ally = original.actors[7], original.actors[-7]
        protector.position, ally.position = (-8, -7, -1), (-6, -7, -1)
        ally.team = 0
        protector.turn_count = ally.turn_count = 0
        if native_scenario:
            self.assertEqual(protector.hp, protector.max_hp)
            self.assertEqual((ally.hp, ally.max_hp), (8784, 8784))
            self.assertEqual(ally.effective_level, 190)
            creature = dict(creature, level=ally.effective_level)
        else:
            set_hp_raw_current(protector, protector.max_hp)
        attacker = Actor(
            8,
            1,
            (-6, -6, -1),
            attacker_character["max_hp"],
            6,
            3,
            8,
            200,
            4,
            True,
            max_hp=attacker_character["max_hp"],
        )
        build_player_snapshot(
            attacker_character, attacker, wp_current=6, wp_maximum=6, running_effects=()
        ).install(attacker)
        terrain = local_arena(
            1134,
            0,
            protector.position,
            [ally.position, attacker.position],
            relocate_monsters=False,
        )
        fight = Fight(
            78,
            [protector, ally, attacker],
            terrain["validated_cells"],
            {0: {protector.position, ally.position}, 1: {attacker.position}},
            terrain["valid_edges"],
        )
        fight.native_qi_snapshot = {
            name: terrain[name] for name in ("x", "y", "width", "height", "cell_masks")
        }
        fight.native_qi_surface_provenance = dict(
            terrain["native_qi_surface_provenance"]
        )
        freeze_terrain(fight)
        initialize_global_pv_collections(fight, (7, -7, 8))
        install_fresh_actor_slots(
            fight,
            prepare_fresh_actor_slots(
                fight,
                physical_radii={
                    identity: actor.physical_radius
                    for identity, actor in fight.actors.items()
                },
            ),
        )
        fight.ready(3)
        fight.ready(4)
        fight.native_effect_uid_next = 1
        characters = {7: character, 8: attacker_character}
        # The guide scenario needs a real non-linear owned attack after the
        # genuine Sacrifice swap; older focused fixtures keep their exact deck.
        decks = {
            7: encode_deck([5044, *extra_active]),
            8: encode_deck([6266, 6269] if native_scenario else [6266]),
        }
        return characters, {-7: creature}, decks, fight

    def run_attack(
        self,
        before_attack=None,
        *,
        return_context=False,
        extra_active=(),
        native_scenario=False
    ):
        from wakfu_server.combat_server_spell import (
            prepare_server_initialization,
            prepare_server_spell,
            server_runtime,
            prepare_server_turn_start,
            prepare_server_turn_end,
        )
        from wakfu_server.combat_runtime_messages import RuntimeMessages
        import sys
        from pathlib import Path

        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
        from combat_audit_turns import advance_actual_turn

        characters, monsters, decks, fight = self.fixture(
            extra_active=extra_active,
            native_scenario=native_scenario,
        )
        rng = random.Random(0)
        common = dict(player_characters=characters, deck_blobs=decks)
        fight, _ = prepare_server_initialization(
            characters[7],
            monsters,
            fight,
            3,
            decks[7],
            action_id=1,
            rng=rng,
            fight_start=False,
            **common,
        )
        fight, _ = prepare_server_initialization(
            characters[8],
            monsters,
            fight,
            4,
            decks[8],
            action_id=2,
            rng=rng,
            fight_start=True,
            **common,
        )

        def cast(identity, spell, target, state, action):
            from wakfu_server.combat_los import authoritative_visible
            from wakfu_server.combat_obstacle_condition import footprint

            def native_los(source, destination, preview):
                return authoritative_visible(
                    characters[identity]["map_id"],
                    source,
                    destination,
                    preview,
                    blocking_footprints={
                        actor.id: footprint(actor.position, actor.physical_radius)
                        for actor in preview.actors.values()
                        if actor.hp > 0
                    },
                )

            return prepare_server_spell(
                struct.pack(
                    ">qqiih",
                    identity,
                    (identity << 32) | spell,
                    *state.actors[target].position,
                ),
                characters[identity],
                monsters,
                state,
                characters[identity]["account_id"],
                decks[identity],
                action_id=action,
                line_of_sight=native_los if return_context else lambda *args: True,
                critical=False,
                rng=rng,
                **common,
            )

        runtime = RuntimeMessages(
            fight,
            turn_start_provider=lambda preview, **kwargs: prepare_server_turn_start(
                characters[7], monsters, preview, decks[7], rng=rng, **common, **kwargs
            ),
            turn_end_provider=lambda preview, **kwargs: prepare_server_turn_end(
                characters[7], monsters, preview, decks[7], rng=rng, **common, **kwargs
            ),
            expiration_runtime_factory=lambda *, action_id: server_runtime(
                characters[7],
                monsters,
                decks[7],
                action_id=action_id,
                critical=False,
                rng=rng,
                **common,
            )[0],
        )
        for _ in range(4):
            if runtime.fight.current.id == 7:
                break
            advance_actual_turn(runtime)
        self.assertEqual(runtime.fight.current.id, 7)
        protected = cast(7, 5044, -7, runtime.fight, 2)
        runtime.fight = protected.fight
        self.assertIn(
            89,
            {
                state.reference
                for state in runtime.fight.actors[-7].state_ledger.entries
            },
        )
        for _ in range(4):
            if runtime.fight.current.id == 8:
                break
            advance_actual_turn(runtime)
        self.assertEqual(runtime.fight.current.id, 8)
        if before_attack is not None:
            before_attack(runtime.fight)
        before = {
            identity: (actor.hp, actor.position)
            for identity, actor in runtime.fight.actors.items()
        }
        attacked = cast(8, 6266, -7, runtime.fight, 10)
        if return_context:
            return attacked, runtime, before, characters, monsters, decks, rng
        return attacked, runtime.fight, before

    def test_direct_owned_attack_redirects_damage_then_swaps_at_cast_boundary(self):
        attacked, original, before = self.run_attack()
        self.assertIn(
            4800, {state.reference for state in original.actors[7].state_ledger.entries}
        )
        self.assertNotIn(
            4800,
            {state.reference for state in original.actors[-7].state_ledger.entries},
        )
        self.assertEqual(attacked.fight.actors[-7].hp, before[-7][0])
        self.assertLess(attacked.fight.actors[7].hp, before[7][0])
        self.assertEqual(attacked.fight.actors[7].position, before[-7][1])
        self.assertEqual(attacked.fight.actors[-7].position, before[7][1])
        self.assertEqual(original.actors[7].position, before[7][1])

    def test_redirect_crossing_low_hp_threshold_removes_sacrifice_and_owner_state(self):
        from wakfu_server.combat_hp_raw import set_hp_raw_current

        def near_threshold(fight):
            protector = fight.actors[7]
            set_hp_raw_current(protector, protector.max_hp // 10 + 1)

        attacked, original, before = self.run_attack(near_threshold)
        self.assertEqual(attacked.fight.actors[-7].hp, before[-7][0])
        self.assertLess(
            attacked.fight.actors[7].hp * 10, attacked.fight.actors[7].max_hp
        )
        self.assertNotIn(
            89,
            {
                state.reference
                for state in attacked.fight.actors[-7].state_ledger.entries
            },
        )
        self.assertNotIn(
            4800,
            {
                state.reference
                for state in attacked.fight.actors[7].state_ledger.entries
            },
        )
        self.assertIn(
            89, {state.reference for state in original.actors[-7].state_ledger.entries}
        )

    def test_redirect_self_loss_heart_reconnect_and_expiry_use_real_turns(self):
        """Protect an ally, consume actual self-loss, restore, then expire protection."""
        from types import SimpleNamespace
        from wakfu_server.combat_actor import (
            actual_actor_stats,
            actual_monster_actor_stats,
        )
        from wakfu_server.combat_remote_effects import active_actor_effects
        from wakfu_server.breed_resources import live_wp
        from wakfu_server.combat_reconnect_snapshot import owned_snapshot
        from wakfu_server.combat_protocol_reconstruction import decode_packet
        from wakfu_server.combat_shared import SharedFight
        from wakfu_server.combat_spell_grant import granted_spells
        from wakfu_server.combat_server_spell import prepare_server_spell
        from wakfu_server.combat_terrain import local_arena
        from wakfu_server.combat_effect_dispatch import EffectDispatcher
        from wakfu_server.fight_checkpoint_store import snapshot
        from combat_audit_turns import advance_actual_turn
        from unittest.mock import patch

        attacked, runtime, before, characters, monsters, decks, rng = self.run_attack(
            return_context=True,
            extra_active=(5028,),
            native_scenario=True,
        )
        self.assertEqual(attacked.fight.actors[-7].hp, before[-7][0])
        self.assertLess(attacked.fight.actors[7].hp, before[7][0])
        self.assertEqual(attacked.fight.actors[7].position, before[-7][1])
        self.assertEqual(attacked.fight.actors[-7].position, before[7][1])
        runtime.fight = attacked.fight
        runtime.action_id = attacked.action_id
        runtime.prepare_delivery(attacked.packets)
        common = dict(player_characters=characters, deck_blobs=decks)

        def cast(identity, reference, target_id, *, granted=False):
            from wakfu_server.combat_los import authoritative_visible
            from wakfu_server.combat_obstacle_condition import footprint

            def native_los(source, destination, preview):
                return authoritative_visible(
                    characters[identity]["map_id"],
                    source,
                    destination,
                    preview,
                    blocking_footprints={
                        actor.id: footprint(actor.position, actor.physical_radius)
                        for actor in preview.actors.values()
                        if actor.hp > 0
                    },
                )

            fight = runtime.fight
            character = characters[identity]
            uid = (
                granted_spells(fight, identity)[reference]["uid"]
                if granted
                else (identity << 32) | reference
            )
            source = snapshot(fight)
            transaction = prepare_server_spell(
                struct.pack(">qqiih", identity, uid, *fight.actors[target_id].position),
                character,
                monsters,
                fight,
                character["account_id"],
                decks[identity],
                action_id=runtime.action_id + 1,
                line_of_sight=native_los,
                critical=False,
                rng=rng,
                **common,
            )
            self.assertEqual(snapshot(fight), source)
            runtime.fight = transaction.fight
            runtime.action_id = transaction.action_id
            runtime.prepare_delivery(transaction.packets)
            return transaction

        for _ in range(8):
            if runtime.fight.current.id == 7:
                break
            advance_actual_turn(runtime)
        self.assertEqual(runtime.fight.current.id, 7)
        self.assertIn(6065, granted_spells(runtime.fight, 7))
        self.assertIn(
            89, {s.reference for s in runtime.fight.actors[-7].state_ledger.entries}
        )
        before_blood = runtime.fight.actors[7].hp
        blood = cast(7, 5028, 8)
        self.assertEqual(blood.plan["costs"]["ap"], 3)
        injured_hp = runtime.fight.actors[7].hp
        loss = before_blood - injured_hp
        self.assertGreater(loss, 0)
        self.assertIn(
            4840, {s.reference for s in runtime.fight.actors[7].state_ledger.entries}
        )
        # Native 4840 stores an integer percentage, not the earlier rounded
        # HP loss. eXs.fOA -> eYE.a -> UP.bt samples this percentage afresh.
        import math
        from wakfu_server.combat_healing_handler import NativeHealingHandler
        from wakfu_server.combat_hp_raw import hp_raw_current

        source_max_hp = runtime.fight.actors[7].max_hp
        stored = [
            state.level
            for state in runtime.fight.actors[7].state_ledger.entries
            if state.reference == 4840
        ]
        self.assertEqual(len(stored), 1)
        stored_percent = stored[0]
        self.assertEqual(hp_raw_current(runtime.fight.actors[7]), injured_hp)
        observed_heart = []
        calculate = NativeHealingHandler._calculate

        def observe_heart(handler, effect, invocation, **kwargs):
            if invocation.reference != 416656:
                return calculate(handler, effect, invocation, **kwargs)
            self.assertEqual(effect["effect_class"], 25)
            self.assertEqual(effect["parameters"], (0.0, 1.0, 0.0, 0.0, 1.0, 0.0))
            self.assertEqual((invocation.caster_id, invocation.target_id), (7, 7))
            self.assertEqual(invocation.level, stored_percent)
            self.assertEqual(handler.fight.actors[7].max_hp, source_max_hp)
            delegated_rng = handler.rng
            draws = []

            def record_draw():
                value = delegated_rng()
                draws.append(value)
                return value

            handler.rng = record_draw
            try:
                result = calculate(handler, effect, invocation, **kwargs)
            finally:
                handler.rng = delegated_rng
            observed_heart.append((draws, result[1]))
            return result

        with patch.object(NativeHealingHandler, "_calculate", observe_heart):
            recovered = cast(7, 6065, 7, granted=True)
        self.assertEqual(recovered.plan["costs"]["ap"], 1)
        self.assertEqual(recovered.plan["costs"]["wp"], 1)
        self.assertEqual(len(observed_heart), 1)
        draws, calculated_heal = observed_heart[0]
        # Independent original eYE/UP arithmetic: Java int multiply, float32
        # conversion/division, floor, then GT.l's strict sample < fraction.
        f32 = lambda value: struct.unpack(">f", struct.pack(">f", value))[0]
        product = ((source_max_hp * stored_percent + (1 << 31)) % (1 << 32)) - (1 << 31)
        native_percent = f32(f32(product) / f32(100))
        floor = math.floor(native_percent)
        fraction = native_percent - floor
        self.assertEqual(len(draws), int(fraction != 0))
        expected_heal = max(1, floor + (int(draws[0] < fraction) if fraction else 0))
        self.assertEqual(calculated_heal, expected_heal)
        self.assertEqual(
            runtime.fight.actors[7].hp - injured_hp,
            min(expected_heal, source_max_hp - injured_hp),
        )
        self.assertGreater(runtime.fight.actors[7].effect_stats[97], 0)
        self.assertNotIn(
            4840, {s.reference for s in runtime.fight.actors[7].state_ledger.entries}
        )
        self.assertNotIn(
            9312, {s.reference for s in runtime.fight.actors[7].state_ledger.entries}
        )

        arena = local_arena(
            1134,
            0,
            (-8, -7, -1),
            [(-6, -7, -1), (-6, -6, -1)],
            relocate_monsters=False,
        )
        self.assertEqual(
            runtime.fight.native_qi_snapshot,
            {key: arena[key] for key in ("x", "y", "width", "height", "cell_masks")},
        )
        shared = SharedFight(
            runtime.fight,
            1134,
            0,
            runtime,
            join_context=dict(
                arena=arena,
                terrain_effect_id=46,
                terrain_instance_id=0,
                leaders={0: 7, 1: 8},
            ),
        )

        def actor_payload(fight, actor, session):
            wp = live_wp(fight, actor.id)
            if actor.controlled:
                stats = actual_actor_stats(
                    characters[actor.id],
                    actor,
                    fight.id,
                    fight=fight,
                    wp_current=wp[0],
                    wp_maximum=wp[1],
                )
            else:
                stats = actual_monster_actor_stats(
                    monsters[actor.id],
                    actor,
                    fight.id,
                    fight=fight,
                    wp_current=wp[0],
                    wp_maximum=wp[1],
                )
            return stats, active_actor_effects(fight, actor.id)

        saved = snapshot(runtime.fight, runtime=runtime)
        saved_rng = rng.getstate()
        # Recovery must serialize already-evaluated carriers, never rerun children.
        with patch.object(
            EffectDispatcher,
            "execute",
            side_effect=AssertionError("Recovery executed gameplay"),
        ):
            packets = owned_snapshot(
                runtime.fight,
                shared,
                SimpleNamespace(account_id=3),
                actor_payload=actor_payload,
            )
        self.assertEqual(snapshot(runtime.fight, runtime=runtime), saved)
        self.assertEqual(rng.getstate(), saved_rng)
        self.assertEqual(packets[0][0], 12847)
        self.assertIn(12053, [opcode for opcode, _ in packets])
        self.assertIn(12514, [opcode for opcode, _ in packets])
        carriers = [
            decode_packet(opcode, body)["effect"]
            for opcode, body in packets
            if opcode == 12613
        ]
        states = [effect for effect in carriers if effect["family"] == 310]
        self.assertNotIn(4840, {effect["state_id"] for effect in states})
        self.assertIn(89, {effect["state_id"] for effect in states})
        live_states = {
            s.uid: s
            for actor in runtime.fight.actors.values()
            for s in actor.state_ledger.entries
        }
        for effect in states:
            self.assertEqual(effect["state_id"], live_states[effect["uid"]].reference)
            self.assertEqual(effect["level"], live_states[effect["uid"]].level)

        for _ in range(16):
            entries = {
                s.reference
                for actor in runtime.fight.actors.values()
                for s in actor.state_ledger.entries
            }
            if runtime.fight.current.id == 8 and not {89, 4800} & entries:
                break
            advance_actual_turn(runtime)
            self.assertIsNone(runtime.awaiting_ack)
        self.assertEqual(runtime.fight.current.id, 8)
        self.assertNotIn(
            89, {s.reference for s in runtime.fight.actors[-7].state_ledger.entries}
        )
        self.assertNotIn(
            4800, {s.reference for s in runtime.fight.actors[7].state_ledger.entries}
        )
        hp = {uid: actor.hp for uid, actor in runtime.fight.actors.items()}
        positions = {uid: actor.position for uid, actor in runtime.fight.actors.items()}
        followup = cast(8, 6269, -7)
        self.assertEqual(followup.plan["costs"]["ap"], 2)
        self.assertEqual(followup.plan["costs"]["mp"], 0)
        self.assertEqual(followup.plan["costs"]["wp"], 0)
        self.assertEqual(followup.plan["actor_id"], 8)
        self.assertEqual(followup.plan["target_id"], -7)
        self.assertLess(runtime.fight.actors[-7].hp, hp[-7])
        self.assertEqual(runtime.fight.actors[7].hp, hp[7])
        self.assertEqual(
            {uid: actor.position for uid, actor in runtime.fight.actors.items()},
            positions,
        )


if __name__ == "__main__":
    unittest.main()
