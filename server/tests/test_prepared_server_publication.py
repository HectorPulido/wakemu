"""Prepared native publication keeps the Registry's real commit/ACK boundary."""
from copy import deepcopy
import struct
import unittest
from unittest.mock import patch

from test_combat_native_action_ids import NativeActionIdTests
from wakfu_server import combat_shared as shared_module
from wakfu_server import combat_checkpoint_publication as checkpoints
from wakfu_server.combat_shared import Registry, Session, Transition
from wakfu_server.combat_geometry_snapshot import source_snapshot


def fixture():
    runtime = NativeActionIdTests().runtime()
    runtime.fight.end_turn(1, 100, 1)
    session = Session(1, 100, "prepared-owner", 1134, 0)
    registry = Registry(lambda current: current == session)
    shared = registry.register(runtime.fight, session, runtime=runtime)
    return registry, shared, session


def prepared(shared):
    runtime = deepcopy(shared.runtime)
    packets = runtime.end_server_turn(-200, runtime.fight.turn_id)
    return Transition(runtime.fight, runtime, tuple(packets))


def state(shared):
    return (
        source_snapshot(shared.fight),
        shared.sequence,
        deepcopy(vars(shared.ack)),
        shared.runtime.native_action_id,
        shared.runtime.awaiting_ack,
        tuple(shared.runtime.pending),
        {
            key: tuple((batch.sequence, batch.packets) for batch in value)
            for key, value in shared.outboxes.items()
        },
    )


class PreparedServerPublicationTests(unittest.TestCase):
    @patch("wakfu_server.combat_runtime_messages.wall_time", new=lambda _: 1700000000.0)
    def test_prepared_publication_equivalence_copy_elision_and_rejections(self):
        results = []
        original_copy = shared_module.deepcopy
        original_persist = checkpoints.persist_prepared
        for direct in (False, True):
            registry, shared, session = fixture()
            transition = prepared(shared)
            old_fight, old_runtime = shared.fight, shared.runtime
            copies, persisted = [], []

            def clone(value, *args):
                if (
                    type(value) is tuple
                    and len(value) == 2
                    and value[0] is old_fight
                    and value[1] is old_runtime
                ):
                    copies.append(True)
                return original_copy(value, *args)

            def persist(current, fight, runtime, packets):
                self.assertIs(current.fight, old_fight)
                self.assertIs(current.runtime, old_runtime)
                self.assertIs(fight, transition.fight)
                self.assertIs(runtime, transition.runtime)
                persisted.append(tuple(packets))
                return original_persist(current, fight, runtime, packets)

            with patch.object(shared_module, "deepcopy", new=clone), patch.object(
                checkpoints, "persist_prepared", new=persist
            ):
                if direct:
                    sequence = registry.execute_prepared_server(
                        91, -200, transition, expected_sequence=shared.sequence
                    )
                else:
                    sequence = registry.execute_server(
                        91,
                        -200,
                        lambda *_: transition,
                        expected_sequence=shared.sequence,
                    )
            self.assertIs(shared.fight, transition.fight)
            self.assertIs(shared.runtime.fight, shared.fight)
            self.assertEqual(len(copies), 0 if direct else 1)
            self.assertEqual(len(persisted), 1)
            before_ack = state(shared)
            ack = struct.pack(">i", shared.runtime.awaiting_ack)
            released = registry.acknowledge(
                91,
                session,
                ack,
                lambda fight, runtime, body: runtime.acknowledge_turn(body),
            )
            results.append((sequence, persisted, before_ack, released, state(shared)))
        self.assertEqual(results[0], results[1])

        # Reject stale ownership and a failed final persistence before adoption.
        registry, shared, _ = fixture()
        transition = prepared(shared)
        before = state(shared)
        with self.assertRaisesRegex(ValueError, "Stale server"):
            registry.execute_prepared_server(
                91, -200, transition, expected_sequence=shared.sequence + 1
            )
        self.assertEqual(state(shared), before)
        for invalid in (
            Transition(shared.fight, shared.runtime, ()),
            Transition(transition.fight, shared.runtime, ()),
        ):
            with self.assertRaisesRegex(ValueError, "not private"):
                registry.execute_prepared_server(
                    91, -200, invalid, expected_sequence=shared.sequence
                )
            self.assertEqual(state(shared), before)

        def reject(*args):
            raise ValueError("checkpoint rejection")

        with patch.object(checkpoints, "persist_prepared", new=reject):
            with self.assertRaisesRegex(ValueError, "checkpoint rejection"):
                registry.execute_prepared_server(
                    91, -200, transition, expected_sequence=shared.sequence
                )
        self.assertEqual(state(shared), before)
        self.assertIs(shared.runtime.fight, shared.fight)

        # Arbitrary callbacks retain their disposable clone and failure rollback.
        observed = []

        def custom(fight, runtime):
            self.assertIsNot(fight, shared.fight)
            self.assertIsNot(runtime, shared.runtime)
            self.assertIs(runtime.fight, fight)
            fight.actors[-200].hp = 1
            observed.append(True)
            raise ValueError("custom rejection")

        with self.assertRaisesRegex(ValueError, "custom rejection"):
            registry.execute_server(91, -200, custom, expected_sequence=shared.sequence)
        self.assertEqual(observed, [True])
        self.assertEqual(state(shared), before)
