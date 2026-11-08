"""A departing ACK owner cannot bypass Rift checkpoint or successor barriers."""
import struct
import unittest

import test_combat_shared as fixtures
from wakfu_server.combat_shared import Transition


class SkippedSuccessorRuntime:
    def __init__(self, fight):
        self.fight = fight
        self.awaiting_ack = 7

    def acknowledge_turn(self, body):
        if struct.unpack(">i", body)[0] != self.awaiting_ack:
            raise ValueError("Unexpected turn ACK")
        self.fight.rift_wave_state["released"] += 1
        self.awaiting_ack = 8
        return ((12502, b"successor-end"),)


class RiftDisconnectCheckpointTests(unittest.TestCase):
    def test_departure_checkpoints_before_publication_and_arms_remaining_owner_ack(
        self,
    ):
        self.exercise(fail_first=False)

    def test_failed_departure_checkpoint_keeps_authority_and_remaining_ack_can_retry(
        self,
    ):
        self.exercise(fail_first=True)

    def exercise(self, *, fail_first):
        fixture = fixtures.SharedCombatTests()
        fixture.setUp()
        fixture.join()
        registry, shared = fixture.registry, fixture.shared
        shared.fight.ready(1)
        shared.fight.ready(2)
        shared.fight.rift_wave_state = dict(instance_id=77, released=0)
        shared.runtime = SkippedSuccessorRuntime(shared.fight)
        for owner in (fixture.one, fixture.two):
            registry.drain(99, owner)
        attempts = []

        def checkpoint(current, candidate, runtime, packets):
            self.assertEqual(current.connected, {fixture.one.account_id})
            self.assertIsNot(candidate, current.fight)
            self.assertEqual(current.fight.rift_wave_state["released"], 0)
            self.assertEqual(candidate.rift_wave_state["released"], 1)
            self.assertEqual(tuple(current.outboxes[fixture.one.account_id]), ())
            attempts.append(candidate)
            if fail_first and len(attempts) == 1:
                raise ValueError("Checkpoint unavailable")
            current.checkpoint_revision = (current.checkpoint_revision or 0) + 1
            return Transition(candidate, runtime, packets)

        shared.join_context[
            "rift_accepted_action"
        ] = lambda current, candidate, runtime, packets: Transition(
            candidate, runtime, packets
        )
        shared.join_context["rift_checkpoint_action"] = checkpoint
        registry.arm_ack(99, 7)
        body = struct.pack(">i", 7)
        self.assertFalse(
            registry.acknowledge(
                99,
                fixture.one,
                body,
                lambda fight, runtime, body: runtime.acknowledge_turn(body),
            )
        )
        original = shared.fight, shared.runtime
        if fail_first:
            with self.assertRaisesRegex(ValueError, "Checkpoint unavailable"):
                registry.disconnect(fixture.two)
            self.assertEqual((shared.fight, shared.runtime), original)
            self.assertEqual(shared.ack.expected, {1: "first"})
            self.assertTrue(shared.ack.complete)
            self.assertEqual(registry.drain(99, fixture.one), [])
            self.assertTrue(
                registry.acknowledge(
                    99,
                    fixture.one,
                    body,
                    lambda fight, runtime, body: runtime.acknowledge_turn(body),
                )
            )
        else:
            self.assertEqual(registry.disconnect(fixture.two), [99])
        self.assertEqual(shared.fight.rift_wave_state["released"], 1)
        self.assertEqual(shared.runtime.awaiting_ack, 8)
        self.assertEqual(shared.ack.turn, 8)
        self.assertEqual(shared.ack.expected, {1: "first"})
        self.assertEqual(shared.ack.received, set())
        self.assertEqual(len(attempts), 2 if fail_first else 1)
        packets = [
            packet
            for batch in registry.drain(99, fixture.one)
            for packet in batch.packets
        ]
        self.assertEqual(packets, [(12502, b"successor-end")])
        self.assertEqual(list(shared.outboxes[fixture.two.account_id]), [])
