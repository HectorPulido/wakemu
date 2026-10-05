import struct
import unittest
import random
from unittest.mock import patch
from wakfu_server.combat_state import Actor, Fight
from wakfu_server.combat_melee import execute_unarmed, decode_request


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
        self.fight.ready(9)
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
