import struct
import unittest
from copy import deepcopy
from types import SimpleNamespace

from wakfu_ai.bridge.world_shared import run_shared_turn
from wakfu_server.combat_automatic_npc_turn import (
    initial_root_manifest,
    install_root_manifest,
    requires_automatic_npc_turn_end,
)
from wakfu_server.combat_global_pv_collections import initialize_global_pv_collections
from wakfu_server.combat_qi_fight import (
    prepare_fresh_actor_slots,
    install_fresh_actor_slots,
)
from wakfu_server.combat_runtime_messages import RuntimeMessages
from wakfu_server.combat_shared import Registry, Session
from wakfu_server.combat_state import Actor, Fight
from wakfu_server.fight_checkpoint_store import snapshot


class AutomaticNpcTurnTests(unittest.TestCase):
    def fixture(self):
        player = Actor(10, 0, (0, 0, 0), 100, 6, 3, 10, 20, 1, True)
        npc = Actor(-200, 1, (2, 0, 0), 80, 4, 2, 100, 10)
        fight = Fight(
            991,
            [player, npc],
            {(x, 0, 0) for x in range(3)},
            {0: {(0, 0, 0)}, 1: {(2, 0, 0)}},
        )
        fight.native_qi_snapshot = dict(
            x=0, y=0, width=3, height=1, cell_masks=[0, 0, 0]
        )
        for actor in (player, npc):
            actor.native_fight_property_counts = {}
            actor.native_controlled_by_ai = False
            actor.native_turn_suppression_bits = 0
            actor.physical_radius = 0
        initialize_global_pv_collections(
            fight, tuple(fight.actors), controller_registration=True
        )
        qi = prepare_fresh_actor_slots(fight, physical_radii={10: 0, -200: 0})
        install_fresh_actor_slots(fight, qi)
        fight.ready(1)
        self.assertEqual(fight.current.id, -200)
        install_root_manifest(
            fight, initial_root_manifest(fight, {-200: {"id": -200, "ref": 5525}})
        )
        fight.native_start_event_delivered = True
        return fight

    @staticmethod
    def runtime_for(fight, seen):
        def turn_end(original, *, actor_id, action_id):
            from wakfu_server.combat_turn_events import (
                deliver_turn_end,
                deliver_turn_regeneration,
            )

            candidate = deepcopy(original)
            dispatcher = SimpleNamespace(
                native_retention=SimpleNamespace(fight=candidate),
                native_clone_authority=object(),
                replay_event=lambda event, **kwargs: (
                    seen.append(event.event_ids[0]) or ()
                ),
            )
            deliver_turn_end(dispatcher, actor_id=actor_id)
            deliver_turn_regeneration(dispatcher, actor_id=actor_id)
            return candidate, ()

        return RuntimeMessages(fight, clock=lambda: 0.0, turn_end_provider=turn_end)

    def test_manifested_passive_root_uses_shared_native_end_and_ack(self):
        fight = self.fixture()
        self.assertTrue(requires_automatic_npc_turn_end(fight, fight.current))
        self.assertEqual(
            snapshot(fight)["native_ordinary_npc_turn_roots"]["-200"]["reference"], 5525
        )
        one = Session(1, 10, "one", 1134, 0)
        registry = Registry(lambda session: session is one)
        seen = []
        runtime = self.runtime_for(fight, seen)
        shared = registry.register(fight, one, runtime=runtime)
        adapter = SimpleNamespace(registry=registry)
        runner_calls = []

        def runner(native):
            runner_calls.append(native)
            yield [], {}

        list(run_shared_turn(runtime, adapter, one, runner))
        self.assertEqual(runner_calls, [])
        self.assertEqual(shared.sequence, 1)
        self.assertEqual(shared.fight.current.id, 10)
        self.assertEqual(shared.runtime.awaiting_ack, 1)
        self.assertEqual(seen, [1002] * 4 + [1037] * 4)
        self.assertTrue(shared.runtime.fight.native_ordinary_npc_turn_roots["-200"])
        batches = registry.drain(fight.id, one)
        self.assertEqual(len(batches), 1)
        self.assertIn(12502, [opcode for opcode, _ in batches[0].packets])
        self.assertTrue(
            registry.acknowledge(
                fight.id,
                one,
                struct.pack(">i", 1),
                lambda candidate, live, body: live.acknowledge_turn(body),
            )
        )
        self.assertIsNone(shared.runtime.awaiting_ack)

    def test_end_callback_cannot_publish_after_root_controller_changes(self):
        from wakfu_server.combat_controller_registry import transfer_native_controller

        fight = self.fixture()
        before = (
            fight.current.id,
            fight.turn_id,
            dict(fight.native_controller_registry["fighters"]),
        )

        def hostile_end(original, *, actor_id, action_id):
            candidate = deepcopy(original)
            transfer_native_controller(candidate, actor_id, 10)
            return candidate, ()

        runtime = RuntimeMessages(
            fight, clock=lambda: 0.0, turn_end_provider=hostile_end
        )
        with self.assertRaises(ValueError):
            runtime.end_automatic_npc_turn(-200, fight.turn_id)
        self.assertEqual((fight.current.id, fight.turn_id), before[:2])
        self.assertEqual(fight.native_controller_registry["fighters"], before[2])
        self.assertIsNone(runtime.awaiting_ack)

    def test_unattested_and_changed_native_root_authority_fail_closed(self):
        fight = self.fixture()
        actor = fight.current
        del fight.native_ordinary_npc_turn_roots
        self.assertFalse(requires_automatic_npc_turn_end(fight, actor))
        install_root_manifest(
            fight, initial_root_manifest(fight, {-200: {"id": -200, "ref": 5525}})
        )
        self.assertTrue(requires_automatic_npc_turn_end(fight, actor))
        actor.native_controlled_by_ai = True
        self.assertFalse(requires_automatic_npc_turn_end(fight, actor))

    def test_property_114_and_summon_claim_are_not_ordinary_roots(self):
        fight = self.fixture()
        actor = fight.current
        actor.native_fight_property_counts = {114: 1}
        self.assertFalse(requires_automatic_npc_turn_end(fight, actor))
        actor.native_fight_property_counts = {}
        actor.native_summon_source = {"ref": 99, "caster_id": 10}
        self.assertFalse(requires_automatic_npc_turn_end(fight, actor))

    def test_player_and_existing_ack_or_claim_cannot_reenter_root_end(self):
        fight = self.fixture()
        self.assertFalse(requires_automatic_npc_turn_end(fight, fight.actors[10]))
        one = Session(1, 10, "one", 1134, 0)
        registry = Registry(lambda session: session is one)
        runtime = RuntimeMessages(fight, clock=lambda: 0.0)
        shared = registry.register(fight, one, runtime=runtime)
        adapter = SimpleNamespace(registry=registry)
        calls = []

        def runner(native):
            calls.append(native)
            yield [], {}

        shared.native_ai_turn_claim = (-200, 1, "stale")
        self.assertEqual(list(run_shared_turn(runtime, adapter, one, runner)), [])
        self.assertEqual(calls, [])
        self.assertEqual(shared.sequence, 0)
        shared.native_ai_turn_claim = None
        runtime.awaiting_ack = 1
        self.assertEqual(list(run_shared_turn(runtime, adapter, one, runner)), [])
        self.assertEqual(calls, [])
        self.assertEqual(shared.sequence, 0)


if __name__ == "__main__":
    unittest.main()
