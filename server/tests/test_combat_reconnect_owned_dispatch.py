"""Owned native summon reconstruction crosses the real shared ACK boundary."""
from collections import deque
import struct
import unittest
from unittest.mock import patch

from test_combat_reconnect_summon_timeline import fixture, timeline_fields
from test_combat_reconnect_grants import grant
from wakfu_server.combat_geometry_snapshot import source_snapshot
from wakfu_server.combat_reconnect_snapshot import owned_snapshot
from wakfu_server.combat_remote_effects import encode_remote_effects
from wakfu_server.combat_runtime_messages import RuntimeMessages
from wakfu_server.combat_shared import Registry, Session, SharedFight
from wakfu_server.combat_timeline_snapshot import current_wire_turn
from wakfu_server.combat_wire import decode_bootstrap, topology


class OwnedReconnectDispatchTests(unittest.TestCase):
    def test_native_birth_grants_and_two_owner_ack_keep_one_authoritative_turn(self):
        for current_summon in (False, True):
            for previously_acknowledged in (False, True):
                with self.subTest(
                    current_summon=current_summon,
                    previously_acknowledged=previously_acknowledged,
                ):
                    fight, summon, context = fixture(current_summon)
                    # Convert the fixture's hero to a second real owner. Both
                    # accounts observe the same registered fight and terrain.
                    fight.actors[200].owner_id = 2
                    old = Session(1, 100, "old-owner", 1134, 0)
                    peer = Session(2, 200, "peer-owner", 1134, 0)
                    new = Session(1, 100, "new-owner", 1134, 0)
                    live = {old, peer}
                    registry = Registry(lambda session: session in live)
                    runtime = RuntimeMessages(fight, clock=lambda: 10.0)
                    shared = SharedFight(fight, 1134, 0, runtime)
                    shared.join_context = context.join_context
                    shared.participants = {1: old, 2: peer}
                    shared.connected = {1, 2}
                    shared.outboxes = {1: deque(), 2: deque()}
                    registry.fights[fight.id] = shared
                    registry.by_actor = {
                        identity: fight.id for identity in fight.actors
                    }
                    registry.by_character = {
                        identity: fight.id
                        for identity, actor in fight.actors.items()
                        if actor.controlled
                    }
                    ended = fight.current.id
                    counter = fight.turn_id
                    native_end = runtime.end_turn(
                        fight.current.owner_id, ended, current_wire_turn(fight)
                    )
                    shared.ack.arm(counter, (old, peer))
                    registry.publish(fight.id, peer, native_end)
                    registry.drain(fight.id, old)
                    registry.drain(fight.id, peer)
                    if previously_acknowledged:
                        self.assertFalse(
                            registry.acknowledge(
                                fight.id,
                                old,
                                struct.pack(">i", counter),
                                lambda *args: self.fail(
                                    "the peer has not acknowledged"
                                ),
                            )
                        )
                    record, carrier = grant(actor_id=200)
                    encoded = encode_remote_effects((record,))

                    def bootstrap(candidate, view, session):
                        return owned_snapshot(
                            candidate,
                            view,
                            session,
                            actor_payload=lambda state, actor, recipient: (
                                b"authoritative-stats",
                                encoded if actor.id == 200 else bytes(2),
                            ),
                        )

                    before = source_snapshot(fight)
                    live.remove(old)
                    live.add(new)
                    persisted = []
                    with patch(
                        "wakfu_server.combat_spectator_snapshot._retained_carrier_packets",
                        return_value=(carrier,),
                    ):
                        registry.takeover(
                            fight.id,
                            new,
                            bootstrap,
                            persist_takeover=persisted.append,
                        )
                    self.assertEqual(persisted, [old])
                    prefix = registry.drain(fight.id, new)[0].packets
                    boot = decode_bootstrap(prefix[0][1])
                    self.assertEqual(
                        boot["myD"], topology(shared.join_context["arena"])
                    )
                    self.assertNotIn(
                        summon.id, [row["actor_id"] for row in boot["participants"]]
                    )
                    birth = fight.native_summon_creation_deliveries[summon.id]
                    birth_packet = (
                        birth["opcode"],
                        bytes.fromhex(birth["payload_hex"]),
                    )
                    self.assertEqual(prefix.count(birth_packet), 1)
                    # Bind the native UI only after the existing INITIAL SU
                    # has started. Otherwise its initiative observer can sort
                    # an ongoing recovered timeline as though in placement.
                    prefix_opcodes = [opcode for opcode, _ in prefix]
                    self.assertEqual(prefix_opcodes.count(12053), 1)
                    early = prefix_opcodes.index(12053)
                    self.assertLess(early, prefix_opcodes.index(12514))
                    self.assertLess(early, prefix.index(birth_packet))
                    initial = prefix[early][1]
                    self.assertEqual(struct.unpack_from(">i", initial)[0], fight.id)
                    self.assertEqual(initial[15:], boot["myG"])
                    self.assertEqual(initial[21], 0)  # Original INITIAL phase.
                    self.assertNotIn(carrier, prefix)
                    self.assertEqual(
                        shared.ack.received, {1} if previously_acknowledged else set()
                    )
                    with self.assertRaisesRegex(ValueError, "Stale combat session"):
                        registry.acknowledge(
                            fight.id, old, struct.pack(">i", counter), lambda *args: []
                        )
                    # The peer continues receiving ordered events while the
                    # reconnecting owner is still constructing its summon.
                    concurrent = ((12873, b"concurrent-authoritative-change"),)
                    registry.publish(fight.id, peer, concurrent)
                    self.assertEqual(
                        registry.drain(fight.id, peer)[0].packets, concurrent
                    )
                    self.assertEqual(registry.drain(fight.id, new), [])
                    release_calls = []

                    def release(candidate, candidate_runtime, body):
                        release_calls.append(bytes(body))
                        return candidate_runtime.acknowledge_turn(body)

                    self.assertEqual(
                        registry.acknowledge(
                            fight.id,
                            peer,
                            struct.pack(">i", counter),
                            release,
                        ),
                        previously_acknowledged,
                    )
                    self.assertEqual(
                        registry.acknowledge(
                            fight.id,
                            new,
                            struct.pack(">i", counter),
                            release,
                        ),
                        not previously_acknowledged,
                    )
                    resumed = registry.drain(fight.id, new)
                    continuation = resumed[0].packets
                    self.assertEqual(continuation.count(carrier), 1)
                    self.assertEqual(resumed[1].packets, concurrent)
                    recovery = next(
                        body for opcode, body in continuation if opcode == 12053
                    )
                    _, orders, _, index, turn = timeline_fields(recovery[15:])
                    self.assertEqual(orders[0][index], shared.fight.current.id)
                    self.assertEqual(orders[0].count(summon.id), 1)
                    self.assertEqual(turn, shared.fight.turn_id)
                    self.assertEqual(release_calls, [struct.pack(">i", counter)])
                    self.assertIsNone(shared.ack.turn)
                    self.assertIsNone(shared.runtime.awaiting_ack)
                    self.assertNotIn(1, shared.reconnect_presentations)
                    self.assertEqual(source_snapshot(shared.fight), before)
                    self.assertFalse(
                        registry.acknowledge(
                            fight.id,
                            new,
                            struct.pack(">i", counter),
                            release,
                        )
                    )
                    self.assertEqual(len(release_calls), 1)
                    # Exercise the reported operation, rather than treating a
                    # clear awaiting_ack field as proof that passing works.
                    for _ in range(len(shared.fight.actors)):
                        current = shared.fight.current
                        next_counter = shared.fight.turn_id
                        if current.controlled:
                            current_session = shared.participants[current.owner_id]
                            registry.execute(
                                fight.id,
                                current_session,
                                current.id,
                                lambda candidate, candidate_runtime: candidate_runtime.end_turn(
                                    current.owner_id,
                                    current.id,
                                    current_wire_turn(candidate),
                                ),
                            )
                        else:
                            registry.execute_server(
                                fight.id,
                                current.id,
                                lambda candidate, candidate_runtime: candidate_runtime.end_server_turn(
                                    current.id, candidate.turn_id
                                ),
                                expected_sequence=shared.sequence,
                            )
                        self.assertEqual(shared.runtime.awaiting_ack, next_counter)
                        self.assertGreater(shared.fight.turn_id, next_counter)
                        self.assertFalse(
                            registry.acknowledge(
                                fight.id,
                                peer,
                                struct.pack(">i", next_counter),
                                release,
                            )
                        )
                        self.assertTrue(
                            registry.acknowledge(
                                fight.id,
                                new,
                                struct.pack(">i", next_counter),
                                release,
                            )
                        )
                        self.assertIsNone(shared.runtime.awaiting_ack)
                        if current.controlled:
                            break
                    else:
                        self.fail("No owned turn followed the native NPC progression")


if __name__ == "__main__":
    unittest.main()
