"""Owner and observer restore the same public eWE PI operand, read-only."""
from dataclasses import asdict
from types import SimpleNamespace
import unittest

import test_combat_spectator_snapshot as spectator_fixture
from wakfu_server.combat_death_script import NativeDeathScriptHandler
from wakfu_server.combat_death_script_snapshot import immediate_death_script_packet
from wakfu_server.combat_effect_dispatch import EffectInvocation
from wakfu_server.combat_reconnect_snapshot import owned_snapshot
from wakfu_server.combat_reproduction_state import encode_state
from wakfu_server.combat_retained_effects import RetainedEffect
from wakfu_server.combat_runtime_messages import RuntimeMessages
from wakfu_server.combat_spectator_snapshot import current_snapshot
from wakfu_server.combat_stat_handler import StatExecutionContext


class DeathScriptRecipientSnapshotTests(unittest.TestCase):
    def fixture(self, *, retained=False):
        fight, shared = spectator_fixture.shared_fixture()
        fight.ready(1)
        shared.runtime = RuntimeMessages(fight, clock=lambda: 0.0)
        shared.runtime.native_action_id = 5
        shared.runtime.turn_deadline = None
        actor = fight.actors[5]
        packets = []
        handler = NativeDeathScriptHandler(
            fight,
            packets,
            action_id=5,
            allocate_uid=lambda: 101,
            context=lambda *args: StatExecutionContext(
                True, True, None, retained, b"", None
            ),
            rng=lambda: 0,
        )
        effect = dict(
            effect_class=1099,
            parameters=[1100010, 0],
            target_masks=[[] for _ in range(7)],
        )
        invocation = EffectInvocation(185395, 20, actor.id, actor.id, actor.position)
        self.assertTrue(handler(effect, {}, handler.prepare(effect, {}, invocation)))
        if retained:
            # Explicit complete Qf fixture populated from the actual handler's
            # retained runner; no immediate operand is manufactured here.
            record = RetainedEffect(101, actor.id, 1099, 185395, manager_id=actor.id)
            fight.native_retained_records[101] = asdict(record)
            fight.native_retained_order.append(101)
        return fight, shared, actor, packets

    def snapshots(self, fight, shared):
        before = encode_state(shared.runtime)
        owner = owned_snapshot(
            fight,
            shared,
            SimpleNamespace(account_id=1, character_id=5),
            actor_payload=lambda state, actor, session: spectator_fixture.actor_payload(
                state, actor
            ),
        )
        observer = current_snapshot(
            fight,
            shared,
            actor_payload=spectator_fixture.actor_payload,
            deadline_ms=123456,
        )
        self.assertEqual(encode_state(shared.runtime), before)
        return owner, observer

    def test_visible_immediate_operand_is_restored_exactly_once_for_both_roles(self):
        fight, shared, actor, live = self.fixture()
        expected = immediate_death_script_packet(
            fight, actor, shared.runtime.native_action_id
        )
        self.assertEqual(expected, live[0])
        self.assertNotIn(101, fight.owned_stat_effects)
        for packets in self.snapshots(fight, shared):
            self.assertEqual(packets.count(expected), 1)
            index = packets.index(expected)
            self.assertGreater(index, 0)
            self.assertEqual(expected[1][12], 1)  # Evaluated immediate execution.

    def test_retained_runner_is_restored_once_without_immediate_reexecution(self):
        fight, shared, actor, _ = self.fixture(retained=True)
        self.assertIsNone(immediate_death_script_packet(fight, actor, 5))
        for packets in self.snapshots(fight, shared):
            carriers = [body for opcode, body in packets if opcode == 12613]
            self.assertEqual(len(carriers), 1)
            self.assertEqual(carriers[0][12], 0)  # Qf restore, not PI execution.

    def test_hidden_final_actor_does_not_leak_immediate_operand_to_either_role(self):
        from wakfu_server.combat_global_pv_collections import (
            initialize_global_pv_collections,
            set_global_fighter_status,
        )

        fight, shared, actor, _ = self.fixture()
        expected = immediate_death_script_packet(fight, actor, 5)
        initialize_global_pv_collections(fight, tuple(fight.actors))
        set_global_fighter_status(fight, actor.id, "OUT_OF_PLAY")
        for packets in self.snapshots(fight, shared):
            self.assertNotIn(expected, packets)

    def test_invalid_immediate_provenance_rejects_both_roles_without_mutation(self):
        fight, shared, actor, _ = self.fixture()
        actor.native_immediate_death_script["producer"] = "foreign"
        before = encode_state(shared.runtime)
        producers = (
            lambda: owned_snapshot(
                fight,
                shared,
                SimpleNamespace(account_id=1),
                actor_payload=lambda state, actor, session: spectator_fixture.actor_payload(
                    state, actor
                ),
            ),
            lambda: current_snapshot(
                fight,
                shared,
                actor_payload=spectator_fixture.actor_payload,
                deadline_ms=123456,
            ),
        )
        for produce in producers:
            with self.assertRaisesRegex(ValueError, "provenance"):
                produce()
            self.assertEqual(encode_state(shared.runtime), before)

    def test_placement_bootstrap_does_not_execute_immediate_operand(self):
        fight, shared, actor, _ = self.fixture()
        expected = immediate_death_script_packet(fight, actor, 5)
        # Explicit phase input isolates snapshot policy from effect admission.
        fight.phase = "placement"
        shared.join_context.update(
            duration_ms=30000,
            actor_payload=lambda state, actor, session: spectator_fixture.actor_payload(
                state, actor
            ),
        )
        for packets in self.snapshots(fight, shared):
            self.assertNotIn(expected, packets)
