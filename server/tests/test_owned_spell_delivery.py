"""Transfer only caller-private spell delivery graphs, retaining direct rollback."""
from contextlib import nullcontext
from copy import deepcopy
import sys
import unittest
from unittest.mock import patch

from test_combat_spell_transaction import SpellTransactionTests
from test_combat_prepared_delivery_transaction import (
    PreparedSpellDeliveryCompositionTests,
)
from wakfu_server.combat_shared import Registry, Session, Transition
from wakfu_server.combat_runtime_messages import RuntimeMessages
from wakfu_server.combat_state import Fight
from wakfu_server.combat_spell_commit import commit_spell_transaction
from wakfu_server.combat_owned_spell_delivery import owned_spell_delivery, _CURRENT
from wakfu_server.combat_pending_restoration import SOURCE
from wakfu_server.combat_native_action_ids import MAX_NATIVE_ACTION_ID
from wakfu_server.combat_geometry_snapshot import source_snapshot
from wakfu_server.combat_characteristic_link import bind_characteristic_stats


def state(shared):
    runtime = shared.runtime
    return (
        source_snapshot(shared.fight),
        shared.sequence,
        deepcopy(vars(shared.ack)),
        runtime.action_id,
        runtime.native_action_id,
        runtime.awaiting_ack,
        tuple(runtime.pending),
        runtime.last_native_delivery,
        {
            key: tuple((batch.sequence, batch.packets) for batch in value)
            for key, value in shared.outboxes.items()
        },
    )


class OwnedSpellDeliveryTests(unittest.TestCase):
    def fixture(self):
        fixture = SpellTransactionTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        fixture.fight.actors[7].native_death_status = {"pending_restoration": SOURCE}
        bind_characteristic_stats(fixture.fight)
        runtime = RuntimeMessages(fixture.fight)
        session = Session(3, 7, "owned-spell", 999999, 0)
        registry = Registry(lambda current: current == session)
        shared = registry.register(fixture.fight, session, runtime=runtime)
        return fixture, registry, shared, session

    def operation(self, fixture, escaped, enabled):
        def cast(candidate, runtime):
            fixture.fight = candidate
            transaction = fixture.execute()
            escaped["transaction"] = transaction  # Test observes discarded inputs.
            escaped["runtime"] = runtime
            with owned_spell_delivery(runtime, transaction, enabled=enabled):
                packets = commit_spell_transaction(
                    runtime, transaction, stats_serializer=lambda *_: b"stats"
                )
            return Transition(transaction.fight, runtime, packets)

        return cast

    def test_real_registry_transfer_equivalence_failure_and_direct_fallback(self):
        outputs, copies = [], []
        for enabled in (False, True):
            fixture, registry, shared, session = self.fixture()
            original_fight, original_runtime = shared.fight, shared.runtime
            source = source_snapshot(original_fight)
            escaped, counts = {}, [0, 0]
            codes = (Fight.__deepcopy__.__code__, RuntimeMessages.__deepcopy__.__code__)

            def observe(frame, event, arg):
                if event == "call":
                    for index, code in enumerate(codes):
                        if frame.f_code is code:
                            counts[index] += 1

            sys.setprofile(observe)
            try:
                registry.execute(
                    77, session, 7, self.operation(fixture, escaped, enabled)
                )
            finally:
                sys.setprofile(None)
            copies.append(counts)
            outputs.append(state(shared))
            self.assertEqual(source_snapshot(original_fight), source)
            self.assertIs(original_runtime.fight, original_fight)
            self.assertIs(shared.fight, escaped["transaction"].fight)
            self.assertIs(shared.runtime.fight, shared.fight)
            self.assertIs(shared.fight.actors[7].effect_stats._fight, shared.fight)
            self.assertNotIn(
                "pending_restoration", shared.fight.actors[7].native_death_status
            )
            self.assertIsNone(_CURRENT.get())
        self.assertEqual(outputs[0], outputs[1])
        self.assertEqual(copies[0], [value + 1 for value in copies[1]])
        for failure in ("allocator", "observer"):
            fixture, registry, shared, session = self.fixture()
            if failure == "allocator":
                shared.runtime.native_action_id = MAX_NATIVE_ACTION_ID
            before = state(shared)
            original_fight, original_runtime = shared.fight, shared.runtime
            escaped = {}
            observer = (
                patch(
                    "wakfu_server.combat_invariant_observation.observe_prepared_boundary",
                    side_effect=ValueError("observer rejected"),
                )
                if failure == "observer"
                else nullcontext()
            )
            with observer, self.assertRaises(ValueError):
                registry.execute(77, session, 7, self.operation(fixture, escaped, True))
            self.assertEqual(state(shared), before)
            self.assertIs(shared.fight, original_fight)
            self.assertIs(shared.runtime, original_runtime)
            self.assertIsNot(escaped["runtime"], original_runtime)
            self.assertIsNot(escaped["transaction"].fight, original_fight)
            self.assertIsNone(_CURRENT.get())
        # Actual existing direct API guarantees source AND supplied preview.
        direct = PreparedSpellDeliveryCompositionTests()
        self.addCleanup(direct.doCleanups)
        direct.test_allocator_failure_preserves_source_preview_counters_and_actor_identity()
        direct.test_observer_failure_preserves_both_graphs_after_private_cleanup()
        runtime, transaction = direct.fixture()
        original = runtime.prepare_fight_delivery
        with patch.object(runtime, "prepare_fight_delivery", wraps=original) as custom:
            with owned_spell_delivery(runtime, transaction):
                self.assertIsNone(_CURRENT.get())
                commit_spell_transaction(
                    runtime, transaction, stats_serializer=lambda *_: b"stats"
                )
            self.assertEqual(custom.call_count, 1)
