"""Birth FIFO ordering, real participant ACKs and recovery deferral."""
import struct
import unittest

import test_combat_shared as shared_fixture
from wakfu_server.combat_multiplayer_wire import added
from wakfu_server.combat_runtime_messages import RuntimeMessages
from wakfu_server.combat_shared import Transition
from wakfu_server.combat_shared import Session
from wakfu_server.combat_reconnect_snapshot import owned_snapshot
from wakfu_server.combat_wire import arena, decode_bootstrap
from wakfu_server.fight_checkpoint_store import snapshot
from wakfu_server.combat_timeline_snapshot import current_wire_turn
from wakfu_server.rift_dispatch_combat import finish_accepted_action
from wakfu_server.rift_publication_fence import birth_fence, publish_births_before_ack


class RiftPublicationFenceTests(unittest.TestCase):
    def test_births_wait_for_real_cohort_ack_with_late_ack_disconnect_and_replay(self):
        # Creation-source and native actor-codec semantics have separate focused
        # coverage. These minimal valid envelopes exercise the actual server
        # publication FSM, participant barrier and native delivery allocator.
        for born_during_end in (False, True):
            with self.subTest(born_during_end=born_during_end):
                fixture = shared_fixture.SharedCombatTests()
                fixture.setUp()
                fixture.join()
                registry, shared = fixture.registry, fixture.shared
                fight = shared.fight
                fight.ready(1)
                fight.ready(2)
                fight.rift_wave_state = dict(
                    instance_id=77, wave=2, turn_budget=40, pending_wave=None
                )
                shared.join_context[
                    "rift_accepted_action"
                ] = lambda _shared, candidate, current, packets: finish_accepted_action(
                    candidate,
                    current,
                    packets,
                    initialize_actor=lambda *_: (),
                )
                shared.join_context.update(
                    arena=arena(
                        1134, 0, sorted(fight.walkable), {0: (0, 0, 0), 1: (3, 0, 0)}
                    ),
                    terrain_effect_id=378,
                    terrain_instance_id=-300,
                )
                runtime = RuntimeMessages(fight, clock=lambda: 100.0)
                runtime.turn_deadline, runtime.deadline_turn = 160.0, fight.turn_id
                shared.runtime = runtime
                for session in (fixture.one, fixture.two):
                    registry.drain(99, session)
                births = (
                    (12608, b"\x00\x01\x01" + struct.pack(">q", -200)),
                    added(
                        99,
                        -200,
                        actor_type=0,
                        team=1,
                        stats=b"\x02native-component",
                        effects=b"\x00\x00",
                    ),
                    (13051, struct.pack(">iiii", 99, 1, -1, 2)),
                )
                starting_turn = fight.turn_id
                starting_sequence = fight.sequence

                def publish(candidate, current):
                    if born_during_end:
                        prefix = current.end_turn(1, 10, current_wire_turn(candidate))
                    else:
                        prefix = ()
                    packets = publish_births_before_ack(
                        current,
                        prefix,
                        births,
                        actor_ids=(-200,),
                    )
                    return Transition(candidate, current, packets)

                registry.execute(99, fixture.one, 10, publish)
                published = [
                    packet
                    for batch in registry.drain(99, fixture.one)
                    for packet in batch.packets
                ]
                registry.drain(99, fixture.two)
                opcodes = [opcode for opcode, _ in published]
                self.assertEqual(opcodes.count(13091), 1)
                self.assertNotIn(12053, opcodes)
                self.assertNotIn(12514, opcodes)
                self.assertEqual(birth_fence(shared.fight)["ack_turn"], starting_turn)
                if born_during_end:
                    self.assertLess(opcodes.index(13091), opcodes.index(12502))
                else:
                    self.assertNotIn(12502, opcodes)
                    self.assertEqual(shared.fight.turn_id, starting_turn)
                    self.assertEqual(shared.fight.sequence, starting_sequence)
                    self.assertEqual(shared.runtime.turn_deadline, 160.0)
                # coX cannot cancel the birth queue or supersede its real ACK.
                prior_ack = shared.ack.turn
                self.assertFalse(
                    registry.recover_timeline(
                        99,
                        fixture.one,
                        struct.pack(">i", 99),
                        now_ms=100000,
                    )
                )
                self.assertEqual(shared.ack.turn, prior_ack)
                self.assertIsNotNone(birth_fence(shared.fight))
                self.assertFalse(registry.drain(99, fixture.one))
                # Accepted replay has no pending wave and publishes no birth
                # or destructive timeline; its original fence stays intact.
                replay = finish_accepted_action(
                    shared.fight,
                    shared.runtime,
                    (),
                    initialize_actor=lambda *_: (),
                )
                self.assertFalse(replay.packets)
                if not born_during_end:
                    registry.execute(
                        99,
                        fixture.one,
                        10,
                        lambda candidate, current: current.end_turn(
                            1, 10, current_wire_turn(candidate)
                        ),
                    )
                    for session in (fixture.one, fixture.two):
                        tail = [
                            packet
                            for batch in registry.drain(99, session)
                            for packet in batch.packets
                        ]
                        self.assertIn(12502, [opcode for opcode, _ in tail])
                        self.assertNotIn(12053, [opcode for opcode, _ in tail])
                expected_ack = shared.runtime.awaiting_ack
                self.assertEqual(expected_ack, starting_turn)
                self.assertTrue(
                    any(opcode == 12053 for opcode, _ in shared.runtime.pending)
                )
                if born_during_end:
                    # Both transports leave before confirming12502. The last
                    # owner's new selection receives its genuine replay, not
                    # a fabricated turn or an ACK cancelled behind its back.
                    registry.disconnect(fixture.two)
                    registry.disconnect(fixture.one)
                    unchanged = snapshot(shared.fight)
                    replacement = Session(1, 10, "replacement", 1134, 0)
                    fixture.live.remove(fixture.one)
                    fixture.live.add(replacement)
                    registry.takeover(
                        99,
                        replacement,
                        lambda state, current, session: owned_snapshot(
                            state,
                            current,
                            session,
                            actor_payload=lambda _state, actor, _session: (
                                b"native-component:" + str(actor.id).encode(),
                                b"\x00\x00",
                            ),
                        ),
                        persist_takeover=lambda _previous: None,
                        recover_disconnected=True,
                    )
                    self.assertEqual(snapshot(shared.fight), unchanged)
                    restored = [
                        packet
                        for batch in registry.drain(99, replacement)
                        for packet in batch.packets
                    ]
                    restored_ops = [opcode for opcode, _ in restored]
                    self.assertNotIn(13091, restored_ops)
                    self.assertEqual(restored_ops.count(12502), 1)
                    baseline = decode_bootstrap(
                        next(body for opcode, body in restored if opcode == 12847)
                    )
                    self.assertEqual(
                        {row["actor_id"] for row in baseline["participants"]},
                        set(shared.fight.actors),
                    )
                    self.assertEqual(shared.ack.expected, {1: replacement.generation})
                    with self.assertRaises(ValueError):
                        registry.acknowledge(
                            99,
                            fixture.one,
                            struct.pack(">i", expected_ack),
                            lambda _fight, current, body: current.acknowledge_turn(
                                body
                            ),
                        )
                    self.assertTrue(
                        registry.acknowledge(
                            99,
                            replacement,
                            struct.pack(">i", expected_ack),
                            lambda _fight, current, body: current.acknowledge_turn(
                                body
                            ),
                        )
                    )
                    released = [
                        packet
                        for batch in registry.drain(99, replacement)
                        for packet in batch.packets
                    ]
                    self.assertEqual(sum(opcode == 12053 for opcode, _ in released), 1)
                    self.assertIsNone(birth_fence(shared.fight))
                    self.assertIsNone(shared.runtime.awaiting_ack)
                    continue
                with self.assertRaises(ValueError):
                    registry.acknowledge(
                        99,
                        fixture.one,
                        struct.pack(">i", expected_ack - 1),
                        lambda _fight, current, body: current.acknowledge_turn(body),
                    )
                self.assertFalse(
                    registry.acknowledge(
                        99,
                        fixture.one,
                        struct.pack(">i", expected_ack),
                        lambda _fight, current, body: current.acknowledge_turn(body),
                    )
                )
                self.assertIsNotNone(birth_fence(shared.fight))
                self.assertFalse(registry.drain(99, fixture.one))
                # Departure removes only that transport from the cohort. The
                # remaining owner's actual ACK releases exactly one snapshot.
                registry.disconnect(fixture.two)
                released = [
                    packet
                    for batch in registry.drain(99, fixture.one)
                    for packet in batch.packets
                ]
                self.assertEqual(sum(opcode == 12053 for opcode, _ in released), 1)
                self.assertIsNone(birth_fence(shared.fight))
                self.assertIsNone(shared.runtime.awaiting_ack)
                with self.assertRaises(ValueError):
                    registry.acknowledge(
                        99,
                        fixture.two,
                        struct.pack(">i", expected_ack),
                        lambda _fight, current, body: current.acknowledge_turn(body),
                    )
                self.assertFalse(registry.drain(99, fixture.one))
