"""Native birth recovery stays private, ordered and fenced by a real witness."""
from collections import deque
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import patch
import struct
import unittest

from wakfu_server.combat_shared import Registry, Session, Batch, SharedFight
from wakfu_server.combat_reconnect_birth_stage import (
    BirthPresentation,
    PendingBirthPresentation,
    StagedReconnectPackets,
)


class ReconnectBirthStageTests(unittest.TestCase):
    def state(self, *, marker=True, canonical=False):
        owner = Session(11, 25, "new-osa", 1314, 1)
        peer = Session(10, 67, "peer", 1314, 1)
        registry = Registry(lambda session: session in (owner, peer))
        fight = SimpleNamespace(
            id=423, phase="active", join_aliases={}, rift_wave_state=None
        )
        runtime = SimpleNamespace(awaiting_ack=13, fight=fight)
        shared = SharedFight(fight, 1314, 1, runtime)
        shared.participants = {11: owner, 10: peer}
        shared.connected = {11, 10}
        shared.outboxes = {11: deque(), 10: deque()}
        shared.ack.arm(13, (owner, peer))
        registry.fights[423] = shared
        ending = (12502, struct.pack(">iiiqii", 423, 77, -1, 25, -1, 0))
        original = (ending, (13420, struct.pack(">i", 423)))
        presentation = BirthPresentation(
            counter=13,
            actor_ids=(1462, 1553, 380, 442),
            resume_packets=(
                (12053, b"frozen-real-timeline"),
                (13912, b"frozen-stats"),
                (12613, b"exact649"),
            ),
            marker_packets=original if marker else (),
            canonical_marker=canonical,
        )
        shared.reconnect_presentations[11] = PendingBirthPresentation.bind(
            owner, presentation
        )
        return registry, shared, owner, peer, original

    @staticmethod
    def release(candidate, runtime, body):
        runtime.awaiting_ack = None
        return [(13337, b"actual-next-turn")]

    def test_historical_private_witness_preserves_every_batch_and_other_owner(self):
        registry, shared, owner, peer, _ = self.state()
        prior_ack = deepcopy(shared.ack)
        all_packets = (
            (12613, b"new-summon"),
            (12873, b"damage"),
            (13337, b"later-turn"),
        )
        registry.publish(423, peer, all_packets[:2])
        registry.publish(423, peer, all_packets[2:])
        peer_batches = registry.drain(423, peer)
        self.assertEqual(tuple(p for b in peer_batches for p in b.packets), all_packets)
        self.assertEqual(registry.drain(423, owner), [])
        self.assertFalse(
            registry.recover_timeline(423, owner, struct.pack(">i", 423), now_ms=1)
        )
        self.assertEqual(shared.ack.__dict__, prior_ack.__dict__)
        self.assertFalse(
            registry.acknowledge(423, owner, struct.pack(">i", 13), self.release)
        )
        resumed = registry.drain(423, owner)
        self.assertEqual(
            [b.packets for b in resumed],
            [
                (
                    (12053, b"frozen-real-timeline"),
                    (13912, b"frozen-stats"),
                    (12613, b"exact649"),
                ),
                all_packets[:2],
                all_packets[2:],
            ],
        )
        self.assertEqual(shared.ack.__dict__, prior_ack.__dict__)
        self.assertEqual(
            sum(p == (12613, b"exact649") for b in resumed for p in b.packets), 1
        )

    def test_natural_first_turn_uses_two_real_acks_and_releases_actual_barrier(self):
        registry, shared, owner, peer, original = self.state(marker=False)
        registry.publish(423, peer, ((12873, b"played-during-recovery"),))
        registry.publish(423, peer, original)
        # The first aUM is a private birth witness. The complete original batch
        # remains buffered; its own later aUM produces the canonical second ACK.
        self.assertEqual(registry.drain(423, owner)[0].packets, original)
        self.assertFalse(
            registry.acknowledge(423, owner, struct.pack(">i", 13), self.release)
        )
        self.assertEqual(shared.ack.received, set())
        buffered = registry.drain(423, owner)
        self.assertEqual(buffered[-1].packets, original)
        self.assertFalse(
            registry.acknowledge(423, peer, struct.pack(">i", 13), self.release)
        )
        self.assertTrue(
            registry.acknowledge(423, owner, struct.pack(">i", 13), self.release)
        )
        self.assertIsNone(shared.ack.turn)
        self.assertIsNone(shared.runtime.awaiting_ack)
        self.assertEqual(
            registry.drain(423, owner)[-1].packets, ((13337, b"actual-next-turn"),)
        )

    def test_pending_canonical_witness_rolls_back_if_release_preparation_fails(self):
        registry, shared, owner, peer, _ = self.state(canonical=True)
        shared.ack.received.add(peer.account_id)
        registry.publish(423, peer, ((12873, b"buffered"),))
        pending = shared.reconnect_presentations[11]
        original_ack = deepcopy(shared.ack.__dict__)

        def fail(*args):
            raise ValueError("actual preparation failed")

        with self.assertRaisesRegex(ValueError, "actual preparation failed"):
            registry.acknowledge(423, owner, struct.pack(">i", 13), fail)
        self.assertIs(shared.reconnect_presentations[11], pending)
        self.assertEqual(shared.ack.__dict__, original_ack)
        self.assertEqual(list(shared.outboxes[11]), [])
        self.assertEqual(len(pending.batches), 1)
        self.assertTrue(
            registry.acknowledge(423, owner, struct.pack(">i", 13), self.release)
        )
        self.assertNotIn(11, shared.reconnect_presentations)
        self.assertEqual(
            sum(
                p == (12613, b"exact649")
                for b in registry.drain(423, owner)
                for p in b.packets
            ),
            1,
        )

    def test_invalid_witness_and_transport_overflow_never_change_other_owners(self):
        registry, shared, owner, peer, original = self.state(marker=False)
        old = Session(11, 25, "old-osa", 1314, 1)
        with self.assertRaises(ValueError):
            registry.acknowledge(423, old, struct.pack(">i", 13), self.release)
        with self.assertRaises(ValueError):
            registry.acknowledge(423, owner, struct.pack(">i", 12), self.release)
        shared.runtime.awaiting_ack = 14
        # Crossed first marker fails only the private transport, never publish.
        registry.publish(423, peer, original)
        self.assertTrue(shared.reconnect_presentations[11].overflowed)
        self.assertEqual(registry.drain(423, peer)[-1].packets, original)
        with self.assertRaises(ConnectionError):
            registry.drain(423, owner)
        registry.publish(423, peer, ((12873, b"peer-still-works"),))
        self.assertEqual(
            registry.drain(423, peer)[-1].packets, ((12873, b"peer-still-works"),)
        )

    def test_terminal_cleanup_keeps_original_queue_and_never_restores_active_su(self):
        registry, shared, owner, peer, _ = self.state(marker=False)
        registry.publish(423, peer, ((12613, b"queued-birth"),))
        shared.fight.phase = "finished"
        registry.publish(423, peer, ((13579, b"actual-terminal"),))
        self.assertNotIn(11, shared.reconnect_presentations)
        delivered = tuple(p for b in registry.drain(423, owner) for p in b.packets)
        self.assertEqual(
            delivered, ((12613, b"queued-birth"), (13579, b"actual-terminal"))
        )
        self.assertNotIn(12053, [op for op, _ in delivered])

    def test_buffer_byte_batch_and_time_bounds_are_transport_local(self):
        for setting in ("bytes", "batches", "time"):
            with self.subTest(setting=setting):
                registry, shared, owner, peer, _ = self.state()
                pending = shared.reconnect_presentations[11]
                with patch(
                    "wakfu_server.combat_reconnect_birth_stage.MAX_BUFFER_BYTES",
                    8 if setting == "bytes" else 10000,
                ), patch(
                    "wakfu_server.combat_reconnect_birth_stage.MAX_BUFFER_BATCHES",
                    0 if setting == "batches" else 100,
                ):
                    if setting == "time":
                        pending.deadline = 0
                    registry.publish(423, peer, ((12873, b"bounded-event"),))
                self.assertTrue(pending.overflowed)
                self.assertEqual(len(pending.batches), 0)
                self.assertEqual(pending.buffered_bytes, 0)
                self.assertEqual(
                    registry.drain(423, peer)[-1].packets, ((12873, b"bounded-event"),)
                )
                with self.assertRaises(ConnectionError):
                    registry.drain(423, owner)

    def test_packet_prefix_preserves_frozen_continuation_contract(self):
        _, shared, _, _, _ = self.state()
        presentation = shared.reconnect_presentations[11].presentation
        packets = StagedReconnectPackets(((12847, b"owned"),), presentation)
        prefixed = packets.prefixed(((12608, b"appearance"),))
        self.assertIs(prefixed.presentation, presentation)
        self.assertEqual(tuple(prefixed), ((12608, b"appearance"), (12847, b"owned")))

    def test_takeover_fences_generation_and_preserves_prior_canonical_ack(self):
        registry, shared, owner, peer, _ = self.state(canonical=True)
        replacement = Session(11, 25, "replacement", 1314, 1)
        registry.live_session = lambda session: session in (replacement, peer)
        original = shared.reconnect_presentations[11].presentation
        shared.ack.received.add(11)

        def bootstrap(*args):
            return StagedReconnectPackets(((12847, b"new-generation"),), original)

        registry.takeover(
            423, replacement, bootstrap, persist_takeover=lambda previous: None
        )
        self.assertEqual(shared.ack.received, {11})
        self.assertEqual(shared.ack.expected[11], replacement.generation)
        self.assertEqual(shared.reconnect_presentations[11].session, replacement)
        with self.assertRaises(ValueError):
            registry.acknowledge(423, owner, struct.pack(">i", 13), self.release)
        # The remaining real peer may release the already acknowledged cohort
        # while this transport is still reconstructing its private objects.
        self.assertTrue(
            registry.acknowledge(423, peer, struct.pack(">i", 13), self.release)
        )
        self.assertIsNone(shared.ack.turn)
        self.assertFalse(
            registry.acknowledge(423, replacement, struct.pack(">i", 13), self.release)
        )
        self.assertIsNone(shared.ack.turn)
        self.assertNotIn(11, shared.reconnect_presentations)
        resumed = registry.drain(423, replacement)
        self.assertEqual(resumed[-1].packets, ((13337, b"actual-next-turn"),))

    def test_failed_durable_takeover_keeps_old_presentation_and_mailbox(self):
        registry, shared, owner, peer, _ = self.state(canonical=True)
        replacement = Session(11, 25, "replacement", 1314, 1)
        registry.live_session = lambda session: session in (replacement, peer)
        pending = shared.reconnect_presentations[11]
        before = deepcopy(shared.ack.__dict__)

        def fail(previous):
            raise ValueError("durable takeover failed")

        with self.assertRaisesRegex(ValueError, "durable takeover failed"):
            registry.takeover(
                423,
                replacement,
                lambda *args: StagedReconnectPackets(
                    ((12847, b"uncommitted"),), pending.presentation
                ),
                persist_takeover=fail,
            )
        self.assertIs(shared.reconnect_presentations[11], pending)
        self.assertEqual(shared.participants[11], owner)
        self.assertEqual(shared.ack.__dict__, before)
        self.assertEqual(list(shared.outboxes[11]), [])

    def test_disconnect_discards_only_matching_transport_stage(self):
        registry, shared, owner, peer, _ = self.state()
        old = Session(11, 25, "old-generation", 1314, 1)
        registry.publish(423, peer, ((12873, b"held"),))
        registry.disconnect(old)
        self.assertIn(11, shared.reconnect_presentations)
        registry.disconnect(owner)
        self.assertNotIn(11, shared.reconnect_presentations)
        self.assertEqual(shared.connected, {10})
        self.assertEqual(shared.ack.expected, {10: peer.generation})
        self.assertEqual(shared.ack.received, set())
        self.assertEqual(registry.drain(423, peer)[-1].packets, ((12873, b"held"),))


if __name__ == "__main__":
    unittest.main()
