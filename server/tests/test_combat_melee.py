import struct
import unittest
import random
from unittest.mock import patch
from wakfu_server.combat_state import Actor, Fight
from wakfu_server.combat_melee import execute_unarmed, decode_request
from native_combat_fixture import initialize_fixture_qi


class UnarmedTests(unittest.TestCase):
    def setUp(self):
        self.pc = Actor(7, 0, (0, 0, 0), 60, 6, 3, 10, 1, owner_id=9, controlled=True)
        self.npc = Actor(-7, 1, (1, 0, 0), 20, 3, 3, 0, 1)
        self.fight = Fight(
            1,
            [self.pc, self.npc],
            {(0, 0, 0), (1, 0, 0)},
            {0: {(0, 0, 0)}, 1: {(1, 0, 0)}},
        )
        self.character = dict(id=7, account_id=9, breed=15, level=1, map_id=1134)
        self.monster = dict(id=-7, ref=5525, level=1, map_id=1134, wp=6)
        from wakfu_server.combat_actor_snapshot import (
            build_player_snapshot,
            build_npc_snapshot,
        )

        self.character.update(
            hp=60, max_hp=self.pc.max_hp, builds={}, inventory_items=[]
        )
        self.pc.direction = 0
        self.npc.direction = 3
        build_player_snapshot(
            self.character, self.pc, wp_current=6, wp_maximum=6, running_effects=()
        ).install(self.pc)
        build_npc_snapshot(
            self.monster, self.npc, wp_current=6, wp_maximum=6, running_effects=()
        ).install(self.npc)
        initialize_fixture_qi(self.fight)
        self.fight.ready(9)
        self.fight.native_effect_uid_next = 1
        self.fight.native_obstacle_cells = frozenset()
        self.body = struct.pack(">qqbiih", 7, -1, 15, 1, 0, 0)

    def run_attack(self, **changes):
        options = dict(
            unarmed=True,
            wp_current=6,
            wp_maximum=6,
            action_id=1,
            effect_uid=1,
            critical_chance=0,
            caster_running_effects=[],
            target_running_effects=[],
            caster_bonuses={},
            target_bonuses={},
            mitigate=lambda d, *a: d,
            rng=random.Random(0),
        )
        options.update(changes)
        with patch("wakfu_server.combat_execute.static_visible", return_value=True):
            return execute_unarmed(
                self.body, self.character, [self.monster], self.fight, 9, **options
            )

    def test_production_preview_uses_common_commit_and_unique_native_action_identifiers(
        self,
    ):
        from wakfu_server.combat_spell_commit import commit_spell_transaction
        from wakfu_server.combat_runtime_messages import RuntimeMessages

        transaction = self.run_attack(prepare_only=True)
        self.assertEqual((self.pc.ap, self.npc.hp), (6, 20))
        runtime = RuntimeMessages(self.fight)
        from wakfu_server.combat_actor import (
            actual_actor_stats,
            actual_monster_actor_stats,
        )

        def stats(actor, state):
            if actor.controlled:
                return actual_actor_stats(
                    self.character, actor, state.id, wp_current=6, wp_maximum=6
                )
            return actual_monster_actor_stats(
                self.monster, actor, state.id, wp_current=6, wp_maximum=6
            )

        packets = commit_spell_transaction(runtime, transaction, stats_serializer=stats)
        self.assertEqual(
            (runtime.fight.actors[7].ap, runtime.fight.actors[-7].hp), (3, 17)
        )
        headers = [
            struct.unpack_from(">ii", payload)
            for opcode, payload in packets
            if opcode in (13509, 12613)
        ]
        self.assertGreaterEqual(len(headers), 2)
        self.assertEqual({fight_id for fight_id, _ in headers}, {1})
        self.assertEqual(len({action for _, action in headers}), len(headers))
        self.assertEqual(runtime.action_id, transaction.action_id)
        self.assertEqual(
            {row["request_action_id"] for row in packets.native_actions},
            {transaction.action_id},
        )

    def test_real_unarmed_damage_replay_preserves_native_item_container_12(self):
        from dataclasses import asdict, replace
        from wakfu_server.combat_conditions import ConditionContext, evaluate_condition
        from wakfu_server.combat_event_replay import NativeEventReplay
        from wakfu_server.combat_spell_commit import commit_spell_transaction
        from wakfu_server.combat_runtime_messages import RuntimeMessages
        from wakfu_server.combat_trigger_identifiers import condition_identifiers

        sources = []
        retained_containers = []
        replay = NativeEventReplay.__call__

        def capture_replay(runtime, source, *, authority):
            sources.append(source)
            retained_containers.append(runtime.retention.container(None))
            return replay(runtime, source, authority=authority)

        with patch.object(NativeEventReplay, "__call__", capture_replay):
            transaction = self.run_attack(prepare_only=True)

        # These sources came through item2145 -> wrapper158454 -> damage3597,
        # ordinary damage lifecycle and the production retained-event replay.
        self.assertTrue(sources)
        source = next(row for row in sources if row.generic_effect == 3597)
        self.assertEqual(source.native_container["type"], 12)
        self.assertTrue(
            any(
                descriptor["container_type"] == 12 and identity == 2145
                for descriptor, identity in retained_containers
            )
        )
        # Match production replay's descriptor projection: transient live
        # accumulators belong to the runtime, not the condition source snapshot.
        descriptor = asdict(replace(source, final_modifier=None, runner_modifier=None))
        descriptor.pop("final_modifier")
        descriptor.pop("runner_modifier")
        context = ConditionContext({}, **condition_identifiers(descriptor))
        self.assertEqual(context.triggering_container_type, 12)
        self.assertTrue(
            evaluate_condition("GetTriggeringContainerType() == 12", context)
        )
        self.assertFalse(evaluate_condition("IsTriggeredByIndirectEffect()", context))

        runtime = RuntimeMessages(self.fight)
        before_commit_sources = len(sources)
        packets = commit_spell_transaction(
            runtime, transaction, stats_serializer=lambda *args: b"owned-stats"
        )
        self.assertEqual(len(sources), before_commit_sources)
        self.assertEqual(runtime.fight.actors[7].ap, 3)
        self.assertEqual(runtime.fight.actors[-7].hp, 17)
        self.assertEqual(runtime.fight.native_owned_group_effects, {})
        self.assertEqual(runtime.fight.owned_stat_effects, {})
        self.assertEqual(packets[0][0], 13509)

    def test_yopuka_level_100_initialization_records_real_unarmed_trigger_criteria(
        self,
    ):
        import copy

        from random import Random
        from test_combat_spell_transaction import SpellTransactionTests
        from wakfu_server import combat_effect_dispatch
        from wakfu_server.combat_event_replay import NativeEventReplay
        from wakfu_server.combat_geometry_snapshot import freeze_terrain
        from wakfu_server.combat_melee import execute_unarmed
        from wakfu_server.combat_runtime_adapter import NativeServerRuntimeAdapter
        from wakfu_server.combat_runtime_messages import RuntimeMessages
        from wakfu_server.combat_server_spell import (
            prepare_server_initialization,
            prepare_server_turn_start,
        )
        from wakfu_server.combat_spell_commit import commit_spell_transaction
        from wakfu_server.combat_terrain import local_arena
        from wakfu_server.progression import level_xp
        from wakfu_server.spells import default_deck

        fixture = SpellTransactionTests()
        fixture.setUp()
        character, monster, fight = fixture.native_server_fixture(
            8, 100, native_qi=True, target_distance=1
        )
        character["account_id"] = 3
        character["xp"] = level_xp(100)
        caster_cell, target_cell = (-8, -7, -1), (-7, -7, -1)
        fight.actors[7].position = caster_cell
        fight.actors[-7].position = target_cell
        terrain = local_arena(1134, 7, caster_cell, target_cell)
        fight.walkable = terrain["validated_cells"]
        fight.edges = terrain["valid_edges"]
        freeze_terrain(fight)
        monster.update(
            wp=0,
            max_wp=0,
            hp=fight.actors[-7].hp,
            max_hp=fight.actors[-7].max_hp,
            level=1,
            x=target_cell[0],
            y=target_cell[1],
            z=target_cell[2],
            direction=3,
        )
        initialized, init_packets = prepare_server_initialization(
            character,
            {monster["id"]: monster},
            fight,
            3,
            default_deck(character),
            action_id=1,
            fight_start=True,
        )
        self.assertTrue(init_packets)
        # Initialization owns the start-turn listener 398720. Its melee
        # listener 398721 is installed by the actual 1001 turn boundary.
        self.assertIn(
            398720,
            {
                row["invocation"]["reference"]
                for row in initialized.native_owned_group_effects.values()
            },
        )
        self.assertNotIn(
            398721,
            {
                row["invocation"]["reference"]
                for row in initialized.native_owned_group_effects.values()
            },
        )
        initialized, _ = prepare_server_turn_start(
            character,
            {monster["id"]: monster},
            initialized,
            default_deck(character),
            actor_id=7,
            action_id=1,
            rng=Random(1),
        )
        self.assertIn(
            398721,
            {
                row["invocation"]["reference"]
                for row in initialized.native_owned_group_effects.values()
            },
        )

        melee = UnarmedTests()
        melee.setUp()
        melee.character = character
        melee.monster = monster
        melee.fight = initialized
        melee.pc = initialized.actors[7]
        melee.npc = initialized.actors[-7]
        melee.body = struct.pack(">qqbiih", 7, -1, 15, *target_cell)
        replay_sources = []
        condition_contexts = {}
        condition_results = []
        native_replay = NativeEventReplay.__call__
        native_condition = NativeServerRuntimeAdapter.condition
        evaluate_condition = combat_effect_dispatch.evaluate_condition

        def capture_replay(runtime, source, *, authority):
            replay_sources.append(source)
            return native_replay(runtime, source, authority=authority)

        def capture_condition(adapter, preview, plan, effect, invocation, **kwargs):
            context = native_condition(
                adapter, preview, plan, effect, invocation, **kwargs
            )
            condition_contexts[id(context)] = (
                invocation.reference,
                copy.deepcopy(invocation.native_trigger_context),
            )
            return context

        def capture_evaluation(criteria, context):
            result = evaluate_condition(criteria, context)
            captured = condition_contexts.get(id(context))
            if captured is not None:
                condition_results.append((captured[0], criteria, result, captured[1]))
            return result

        with patch.object(NativeEventReplay, "__call__", capture_replay), patch.object(
            NativeServerRuntimeAdapter, "condition", capture_condition
        ), patch.object(
            combat_effect_dispatch, "evaluate_condition", capture_evaluation
        ):
            with patch("wakfu_server.combat_execute.static_visible", return_value=True):
                transaction = execute_unarmed(
                    melee.body,
                    character,
                    {monster["id"]: monster},
                    initialized,
                    3,
                    unarmed=True,
                    wp_current=6,
                    wp_maximum=6,
                    action_id=1,
                    effect_uid=initialized.native_effect_uid_next,
                    critical_chance=0,
                    caster_running_effects=(),
                    target_running_effects=(),
                    caster_bonuses={},
                    target_bonuses={},
                    mitigate=lambda damage, *_args: damage,
                    rng=Random(1),
                    prepare_only=True,
                )
        actual_hit_sources = [
            source for source in replay_sources if source.generic_effect == 3597
        ]
        self.assertTrue(actual_hit_sources)
        for source in actual_hit_sources:
            self.assertEqual(source.native_container["type"], 12)
        self.assertTrue(
            all(type(result) is bool for _, _, result, _ in condition_results)
        )
        trigger_checks = [
            check
            for check in condition_results
            if check[3] is not None and check[3].get("generic_effect") == 3597
        ]
        self.assertTrue(trigger_checks)
        self.assertTrue(
            all(
                source["native_container"]["type"] == 12
                for _, _, _, source in trigger_checks
            )
        )
        self.assertEqual(transaction.fight.actors[7].ap, 3)
        self.assertLess(transaction.fight.actors[-7].hp, initialized.actors[-7].hp)

        runtime = RuntimeMessages(initialized)
        packets = commit_spell_transaction(
            runtime,
            transaction,
            stats_serializer=lambda *_args: b"native-stats",
        )
        self.assertTrue(packets)
        self.assertEqual(runtime.fight.actors[7].ap, 3)

    def test_native_fists_cost_and_damage(self):
        result = self.run_attack()
        self.assertEqual((self.pc.ap, self.pc.mp, self.npc.hp), (3, 3, 17))
        self.assertEqual(result["packets"][0][0], 13509)
        self.assertIn(12613, [p for p, _ in result["packets"]])
        self.assertEqual(set(result["snapshots"]), {7, -7})

    def test_action_allocation_failure_does_not_commit_damage_or_cost(self):
        from wakfu_server.combat_spell_commit import commit_spell_transaction
        from wakfu_server.combat_runtime_messages import RuntimeMessages
        from wakfu_server.combat_native_action_ids import MAX_NATIVE_ACTION_ID
        from wakfu_server.combat_geometry_snapshot import source_snapshot

        transaction = self.run_attack(prepare_only=True)
        runtime = RuntimeMessages(self.fight)
        runtime.native_action_id = MAX_NATIVE_ACTION_ID - 1
        before = source_snapshot(self.fight)
        from wakfu_server.combat_actor import (
            actual_actor_stats,
            actual_monster_actor_stats,
        )

        def stats(actor, state):
            if actor.controlled:
                return actual_actor_stats(
                    self.character, actor, state.id, wp_current=6, wp_maximum=6
                )
            return actual_monster_actor_stats(
                self.monster, actor, state.id, wp_current=6, wp_maximum=6
            )

        with self.assertRaisesRegex(ValueError, "exhausted"):
            commit_spell_transaction(runtime, transaction, stats_serializer=stats)
        self.assertIs(runtime.fight, self.fight)
        self.assertEqual(source_snapshot(self.fight), before)
        self.assertEqual(runtime.action_id, 0)
        self.assertEqual(runtime.native_action_id, MAX_NATIVE_ACTION_ID - 1)

    def test_failed_encoding_rolls_back(self):
        before = (self.pc.ap, self.npc.hp, len(self.fight.events))
        with self.assertRaises(ValueError):
            self.run_attack(effect_uid=0)
        self.assertEqual((self.pc.ap, self.npc.hp, len(self.fight.events)), before)

    def test_equipment_unknown_effects_and_short_request_rejected(self):
        for values in (
            dict(unarmed=False),
            dict(critical_chance=1),
            dict(target_running_effects=None),
        ):
            with self.assertRaises(ValueError):
                self.run_attack(**values)
        with self.assertRaises(ValueError):
            decode_request(self.body[:-1])
        self.assertEqual(self.pc.ap, 6)

    def test_insufficient_ap_does_not_damage(self):
        self.pc.ap = 2
        with self.assertRaises(ValueError):
            self.run_attack()
        self.assertEqual(self.npc.hp, 20)

    def test_native_unarmed_consumes_armor_before_hp(self):
        self.npc.effect_stats[97] = 7
        result = self.run_attack()
        self.assertEqual(
            (self.pc.ap, self.npc.hp, self.npc.effect_stats[97]), (3, 20, 4)
        )
        self.assertEqual(result["damage"], 0)
        self.assertGreater(self.fight.native_effect_uid_next, 1)

    def test_late_animation_failure_rolls_back_resources_armor_and_uid(self):
        from copy import deepcopy

        self.npc.effect_stats[97] = 2
        before = deepcopy(self.fight.__dict__)
        with patch(
            "wakfu_server.combat_melee.animation", side_effect=ValueError("late codec")
        ):
            with self.assertRaises(ValueError):
                self.run_attack()
        self.assertEqual(
            self.fight.native_effect_uid_next, before["native_effect_uid_next"]
        )
        self.assertEqual(
            (self.pc.ap, self.npc.hp, self.npc.effect_stats[97]), (6, 20, 2)
        )
        self.assertEqual(self.fight.events, before["events"])

    def test_seeded_native_fractional_rounding_matches_shared_arithmetic(self):
        from wakfu_server.equipment_damage import damage

        # Native localization SIDE multiplies base3 by1.1; UP.bt uses the
        # fractional part, not fixed truncation. Seed0/1 cross that threshold.
        for seed in (0, 1):
            self.setUp()
            reference_rng = random.Random(seed)
            expected = damage(
                3,
                3,
                self.pc.effect_stats,
                self.npc.effect_stats,
                critical=False,
                single_target=True,
                area=False,
                melee=True,
                berserk=False,
                front=False,
                localization="SIDE",
                rng=reference_rng.random,
            )
            self.npc.effect_stats[97] = 7
            result = self.run_attack(rng=random.Random(seed))
            self.assertEqual(self.npc.effect_stats[97], 7 - expected)
            self.assertEqual((self.npc.hp, result["damage"]), (20, 0))
        self.assertEqual(
            {random.Random(0).random() < 0.3, random.Random(1).random() < 0.3},
            {False, True},
        )

    def test_external_rng_rolls_back_on_late_failure(self):
        rng = random.Random(1)
        before = rng.getstate()
        with patch(
            "wakfu_server.combat_melee.animation", side_effect=ValueError("late codec")
        ):
            with self.assertRaises(ValueError):
                self.run_attack(rng=rng)
        self.assertEqual(rng.getstate(), before)
        self.assertEqual(
            (self.pc.ap, self.npc.hp, self.fight.native_effect_uid_next), (6, 20, 1)
        )

    def test_serializer_source_mutation_does_not_commit_preview(self):
        rng = random.Random(1)
        before_rng = rng.getstate()

        def changed_source(*args, **kwargs):
            self.pc.hp = 59
            return b""

        with patch(
            "wakfu_server.combat_melee.actual_actor_stats", side_effect=changed_source
        ):
            with self.assertRaisesRegex(ValueError, "changed during unarmed"):
                self.run_attack(rng=rng)
        self.assertEqual((self.pc.ap, self.pc.hp, self.npc.hp), (6, 59, 20))
        self.assertEqual(self.fight.native_effect_uid_next, 1)
        self.assertEqual(rng.getstate(), before_rng)
