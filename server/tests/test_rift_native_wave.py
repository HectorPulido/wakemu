import copy
import unittest
from unittest.mock import patch

from wakfu_server.monsters import owned_instance
from wakfu_server.combat_state import Actor, Fight
from wakfu_server.combat_global_pv_collections import initialize_global_pv_collections
from wakfu_server.combat_qi_fight import (
    prepare_fresh_actor_slots,
    install_fresh_actor_slots,
    current_registry,
)
from wakfu_server.combat_multiplayer_wire import decode_added
from wakfu_server.fight_checkpoint_store import snapshot
from wakfu_server.rift_npc_creation import prepare_wave_npcs, install_native_wave
from wakfu_server.rift_combat_adapter import creation_replay, world_snapshot


class RiftNativeWaveTests(unittest.TestCase):
    def test_wave_initialization_only_initializes_new_roster_and_preserves_history(
        self,
    ):
        from wakfu_server.rift_npc_creation import initialize_native_wave_actors

        fight = self.pending_fight()
        monster = self.monster(-201, 3)
        actor = prepare_wave_npcs([monster])[0]
        fight.actors[actor.id] = actor
        fight.native_npc_ai_actors = frozenset({-200})
        fight.native_npc_initialization_receipts = {-200: {"initialized": True}}
        plans = {-201: (5525, (), ())}

        def initialize(preview, sources, admitted_plans):
            self.assertEqual(set(sources), {-201})
            self.assertEqual(admitted_plans, plans)
            self.assertTrue(preview.actors[-201].native_controlled_by_ai)
            preview.native_npc_initialization_receipts = {-201: {"initialized": True}}

        with patch(
            "wakfu_server.combat_npc_ai_initialization.initial_ai_actors",
            return_value=frozenset({-201}),
        ), patch(
            "wakfu_server.combat_npc_initialization.initial_plans",
            return_value=plans,
        ), patch(
            "wakfu_server.combat_npc_initialization.initialize_ordinary_npcs",
            side_effect=initialize,
        ):
            initialize_native_wave_actors(fight, [monster])
        self.assertEqual(fight.native_npc_ai_actors, frozenset({-200, -201}))
        self.assertEqual(set(fight.native_npc_initialization_receipts), {-200, -201})
        self.assertFalse(fight.actors[-200].native_controlled_by_ai)

    def test_wave_without_initial_states_preserves_existing_initialization_receipts(
        self,
    ):
        from wakfu_server.rift_npc_creation import initialize_native_wave_actors

        fight = self.pending_fight()
        fight.native_npc_initialization_receipts = {-200: {"initialized": True}}
        with patch(
            "wakfu_server.combat_npc_ai_initialization.initial_ai_actors",
            return_value=frozenset(),
        ), patch(
            "wakfu_server.combat_npc_initialization.initial_plans", return_value={}
        ), patch(
            "wakfu_server.combat_npc_initialization.initialize_ordinary_npcs"
        ) as initialize:
            initialize_native_wave_actors(fight, [self.monster(-200, 2)])
        initialize.assert_not_called()
        self.assertEqual(
            fight.native_npc_initialization_receipts, {-200: {"initialized": True}}
        )

    def monster(self, identity, x):
        return owned_instance(5525, 1, identity, map_id=1134, x=x, y=0, z=0)

    def pending_fight(self):
        npc = prepare_wave_npcs([self.monster(-200, 2)])[0]
        pc = Actor(1, 0, (0, 0, 0), 100, 6, 3, 10000, 1, 1, True)
        pc.physical_radius = 0
        fight = Fight(
            7,
            [pc, npc],
            {(x, y, 0) for x in range(4) for y in range(4)},
            {0: {pc.position}, 1: {npc.position}},
        )
        fight.native_qi_snapshot = dict(
            x=0, y=0, width=4, height=4, cell_masks=[0x100] * 16
        )
        initialize_global_pv_collections(fight, tuple(fight.actors))
        install_fresh_actor_slots(
            fight,
            prepare_fresh_actor_slots(
                fight,
                physical_radii={a.id: a.physical_radius for a in fight.actors.values()},
            ),
        )
        fight.rift_wave_state = dict(
            instance_id=9, wave=1, turn_budget=40, wave_actor_ids=[npc.id]
        )
        fight.ready(1)
        fight.apply_damage(pc.id, npc.id, npc.hp)
        return fight

    def test_real_native_wave_stays_in_one_fight_and_preserves_player_turn(self):
        fight = self.pending_fight()
        before_turn = (fight.turn_id, fight.current.id, fight.current.ap)

        def initialize(preview, actor, monster):
            self.assertEqual(preview.actors[actor.id].effect_stats[1], actor.hp)
            self.assertIsNotNone(current_registry(preview))
            return []

        packets = install_native_wave(
            fight, [self.monster(-201, 3)], initialize_actor=initialize
        )
        self.assertEqual((fight.id, fight.phase, fight.winner), (7, "active", None))
        self.assertEqual(
            (fight.turn_id, fight.current.id, fight.current.ap), before_turn
        )
        self.assertEqual(fight.order, [1, -201])
        self.assertEqual([opcode for opcode, _ in packets], [12608, 13091])
        admission = decode_added(packets[1][1])
        self.assertEqual(
            (
                admission["fight_id"],
                admission["actor_id"],
                admission["actor_type"],
                admission["team"],
            ),
            (7, -201, 0, 1),
        )
        self.assertIsNone(admission["controller"])
        self.assertNotIn("native_summon_registrations", vars(fight))
        self.assertFalse(any(e["kind"] == "finished" for e in fight.events))
        saved = snapshot(fight)
        self.assertEqual(
            saved["rift_wave_state"]["staged_receipts"][0],
            dict(
                completed_wave=1,
                actor_ids=[-200],
                turn=1,
                next_actor_ids=[-201],
                next_species_refs=[5525],
            ),
        )
        self.assertEqual(
            [p["opcode"] for p in saved["native_rift_creation_deliveries"]["-201"]],
            [12608, 13091],
        )
        self.assertEqual(creation_replay(fight), tuple(packets))
        self.assertEqual(creation_replay(fight, world_only=True), (packets[0],))

    def test_replay_rejects_foreign_identity_without_mutating_fight(self):
        fight = self.pending_fight()
        install_native_wave(
            fight, [self.monster(-201, 3)], initialize_actor=lambda *a: []
        )
        fight.native_rift_creation_deliveries[-201][1]["payload_hex"] = "00"
        before = snapshot(fight)
        with self.assertRaises(ValueError):
            creation_replay(fight)
        self.assertEqual(snapshot(fight), before)

    def test_same_wave_cannot_be_admitted_twice(self):
        fight = self.pending_fight()
        install_native_wave(
            fight, [self.monster(-201, 3)], initialize_actor=lambda *a: []
        )
        before = snapshot(fight)
        with self.assertRaises(ValueError):
            install_native_wave(
                fight, [self.monster(-202, 1)], initialize_actor=lambda *a: []
            )
        self.assertEqual(snapshot(fight), before)

    def test_occupied_cell_or_reused_identity_reject_before_registration(self):
        for monster in (self.monster(-201, 0), self.monster(-200, 3)):
            with self.subTest(monster=monster["id"]):
                fight = self.pending_fight()
                before = snapshot(fight)
                with self.assertRaises(ValueError):
                    install_native_wave(
                        fight, [monster], initialize_actor=lambda *a: []
                    )
                self.assertEqual(snapshot(fight), before)

    def test_failed_initializer_changes_only_discarded_preview(self):
        fight = self.pending_fight()
        before = snapshot(fight)
        preview = copy.deepcopy(fight)

        def fail(*args):
            raise ValueError("constructor rejected")

        with self.assertRaisesRegex(ValueError, "constructor rejected"):
            install_native_wave(preview, [self.monster(-201, 3)], initialize_actor=fail)
        self.assertEqual(snapshot(fight), before)

    def test_accepted_action_consumes_frozen_roster_and_defers_timeline_until_ack(self):
        from wakfu_server.combat_runtime_messages import RuntimeMessages
        from wakfu_server.rift_dispatch_combat import finish_accepted_action

        fight = self.pending_fight()
        fight.edges = {((x, 0, 0), (x + 1, 0, 0)) for x in range(3)}
        fight.rift_monsters = {-200: self.monster(-200, 2)}
        policy = dict(
            enabled=True,
            policy_kind="local_dev_not_official",
            turn_budget=40,
            max_members=4,
            classic_wave_size=1,
            ultimate_wave_size=1,
            starting_wave=1,
            selection="uniform_with_replacement",
            scaling="native_base_grade",
            quest_requirements=False,
            key_requirements=False,
            rewards="callback_only",
        )
        fight.rift_wave_state.update(
            catalog=dict(
                wave_id=3, map_id=1134, type="INFINITE_WAVE", species_refs=[5525]
            ),
            policy=policy,
            seed="test",
            actor_id_pool=[-201],
        )
        runtime = RuntimeMessages(fight)
        runtime.clock = lambda: 100
        runtime.turn_deadline = 123
        before_turn = fight.turn_id
        result = finish_accepted_action(
            fight, runtime, (), initialize_actor=lambda *a: []
        )
        self.assertIs(result.fight, fight)
        self.assertEqual(fight.turn_id, before_turn)
        self.assertEqual(runtime.turn_deadline, 123)
        self.assertEqual(fight.rift_wave_state["wave"], 2)
        self.assertEqual(fight.rift_wave_state["actor_id_pool"], [])
        self.assertEqual(set(fight.rift_monsters), {-200, -201})
        self.assertEqual([opcode for opcode, _ in result.packets[:2]], [12608, 13091])
        self.assertNotIn(12053, [opcode for opcode, _ in result.packets])
        self.assertTrue(runtime.native_initial_timeline_restore_pending)
        self.assertEqual(fight.native_rift_birth_fence["ack_turn"], before_turn)
        import struct
        from wakfu_server.combat_native_action_ids import NATIVE_ACTION_PACKETS

        if 13051 in NATIVE_ACTION_PACKETS:
            notification = next(
                payload for opcode, payload in result.packets if opcode == 13051
            )
            fight_id, native_action_id, category, wave = struct.unpack(
                ">iiii", notification
            )
            self.assertEqual((fight_id, category, wave), (7, -1, 2))
            self.assertGreater(native_action_id, 0)
        self.assertEqual(len(world_snapshot(fight)), 2)

        # A subsequent ACK must not replay the old one-player timeline.
        second = self.pending_fight()
        second.edges = set(fight.edges)
        second.rift_monsters = {-200: self.monster(-200, 2)}
        second.rift_wave_state.update(
            catalog=fight.rift_wave_state["catalog"],
            policy=policy,
            seed="test",
            actor_id_pool=[-201],
        )
        paused = RuntimeMessages(second)
        from wakfu_server.combat_timeline_snapshot import current_wire_turn

        end_packets = paused.end_turn(1, 1, current_wire_turn(second))
        paused.pending = [(12053, b"obsolete-roster")]
        staged = finish_accepted_action(
            second, paused, end_packets, initialize_actor=lambda *a: []
        )
        staged_codes = [opcode for opcode, _ in staged.packets]
        self.assertLess(staged_codes.index(13091), staged_codes.index(12502))
        self.assertNotIn(12053, staged_codes)
        self.assertTrue(paused.pending)
        self.assertNotIn((12053, b"obsolete-roster"), paused.pending)
        self.assertTrue(any(opcode == 12053 for opcode, _ in paused.pending))
        released = paused.acknowledge_turn(struct.pack(">i", paused.awaiting_ack))
        self.assertTrue(any(opcode == 12053 for opcode, _ in released))
        self.assertIsNone(second.native_rift_birth_fence)

    def test_unregistered_history_cannot_release_or_consume_native_capacity(self):
        from wakfu_server.combat_runtime_messages import RuntimeMessages
        from wakfu_server.rift_dispatch_combat import finish_accepted_action

        fight = self.pending_fight()
        policy = dict(
            enabled=True,
            policy_kind="local_dev_not_official",
            turn_budget=40,
            max_members=4,
            classic_wave_size=1,
            ultimate_wave_size=1,
            starting_wave=1,
            selection="uniform_with_replacement",
            scaling="native_base_grade",
            quest_requirements=False,
            key_requirements=False,
            rewards="callback_only",
        )
        fight.rift_wave_state.update(
            catalog=dict(
                wave_id=3, map_id=1134, type="INFINITE_WAVE", species_refs=[5525]
            ),
            policy=policy,
            seed="test",
            actor_id_pool=[-201],
        )
        # A dead-looking Actor is not registered native history. It must not
        # silently release presentation capacity or manufacture a defeat.
        for identity in range(-1000, -1125, -1):
            actor = Actor(identity, 1, (3, 3, 0), 1, 0, 0, 0, 1)
            actor.hp = 0
            fight.actors[identity] = actor
        runtime = RuntimeMessages(fight)
        with self.assertRaisesRegex(ValueError, "registration"):
            finish_accepted_action(fight, runtime, (), initialize_actor=lambda *a: [])
        self.assertEqual((fight.phase, fight.winner), ("active", None))
        self.assertNotIn("outcome", fight.rift_wave_state)
        self.assertIsNotNone(fight.rift_wave_state["pending_wave"])
        self.assertEqual(fight.rift_wave_state["actor_id_pool"], [-201])


if __name__ == "__main__":
    unittest.main()
