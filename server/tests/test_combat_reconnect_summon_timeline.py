"""Reconnect constructs each summon before authoritative timeline restoration."""
from copy import deepcopy
from types import SimpleNamespace
import struct
import unittest

from test_combat_runtime_messages import RuntimeMessageTests
from wakfu_server.combat_reconnect_snapshot import owned_snapshot
from wakfu_server.combat_geometry_snapshot import source_snapshot
from wakfu_server.combat_wire import decode_bootstrap, decode_actor_state


def fixture(current_summon):
    fight, summon, _ = RuntimeMessageTests._initial_restore_with_innate_summon(100)
    fight.turn_id = 13
    fight.native_timeline_member_counters[str(summon.id)] = 3
    if current_summon:
        fight.turn_index = fight.order.index(summon.id)
    shared = SimpleNamespace(
        map_id=1134,
        runtime=SimpleNamespace(
            turn_deadline=None, native_action_id=41, awaiting_ack=None
        ),
        join_context={
            "arena": dict(
                map_id=1134,
                instance_id=0,
                x=0,
                y=0,
                width=4,
                height=1,
                min_z=0,
                max_z=0,
                cell_masks=[0] * 4,
            ),
            "terrain_effect_id": 99,
            "terrain_instance_id": 0,
            "leaders": {0: 100, 1: -200},
        },
    )
    return fight, summon, shared


def timeline_fields(data):
    round_number, turn, phase, deadline = struct.unpack_from(">hiBq", data)
    cursor = 15
    orders = []
    for _ in range(2):
        count = data[cursor]
        cursor += 1
        orders.append(struct.unpack_from(">" + "q" * count, data, cursor))
        cursor += count * 8
    count = data[cursor]
    cursor += 1
    progress = {}
    for _ in range(count):
        identity, value = struct.unpack_from(">qh", data, cursor)
        progress[identity] = value
        cursor += 10
    index = struct.unpack_from(">b", data, cursor)[0]
    return phase, orders, progress, index, turn


class ReconnectSummonTimelineTests(unittest.TestCase):
    def test_original_pending_or_historical_marker_keeps_real_counter_and_owner(self):
        for pending, historical_actor in ((True, 100), (False, 100), (False, 999999)):
            with self.subTest(pending=pending, historical_actor=historical_actor):
                fight, summon, shared = fixture(True)
                session = SimpleNamespace(account_id=1, character_id=100)
                marker = (
                    (
                        12502,
                        struct.pack(
                            ">iiiqii", fight.id, 40, -1, historical_actor, -1, 0
                        ),
                    ),
                    (13420, struct.pack(">i", fight.id)),
                )
                shared.ack = SimpleNamespace(turn=12, received={1})
                if pending:
                    shared.runtime.awaiting_ack = 12
                    shared.reconnect_turn_end_packets = marker
                else:
                    shared.reconnect_end_turn_history = (12, marker)
                before = source_snapshot(fight)
                packets = owned_snapshot(
                    fight,
                    shared,
                    session,
                    actor_payload=lambda *args: (b"owned-stats", bytes(2)),
                )
                qualified = pending or historical_actor == 100
                self.assertEqual(packets.presentation.counter, 12 if qualified else 13)
                self.assertEqual(
                    packets.presentation.marker_packets, marker if qualified else ()
                )
                self.assertEqual(packets.presentation.canonical_marker, pending)
                initial = decode_bootstrap(packets[0][1])["myG"]
                self.assertEqual(timeline_fields(initial)[-1], 12 if qualified else 13)
                self.assertEqual(shared.ack.received, {1})
                recovery = packets.presentation.resume_packets[0][1]
                self.assertEqual(timeline_fields(recovery[15:])[-1], 13)
                self.assertEqual(source_snapshot(fight), before)

    def test_known_original_marker_bootstraps_on_witness_and_preserves_full_resume(
        self,
    ):
        from wakfu_server.combat_timeline_snapshot import counters

        for pending in (True, False):
            with self.subTest(pending=pending):
                fight, summon, shared = fixture(True)
                marker = (
                    (
                        12502,
                        struct.pack(">iiiqii", fight.id, 40, -1, 100, -1, 0),
                    ),
                    (13420, struct.pack(">i", fight.id)),
                )
                shared.ack = SimpleNamespace(turn=12, received={1})
                if pending:
                    shared.runtime.awaiting_ack = 12
                    shared.reconnect_turn_end_packets = marker
                else:
                    shared.reconnect_end_turn_history = (12, marker)

                before = source_snapshot(fight)
                original_counters = counters(fight)
                original_order = tuple(fight.order)
                original_current = fight.current.id
                packets = owned_snapshot(
                    fight,
                    shared,
                    SimpleNamespace(account_id=1, character_id=100),
                    actor_payload=lambda *args: (b"owned-stats", b"\x00\x00"),
                )

                self.assertEqual(packets.presentation.marker_packets, marker)
                self.assertEqual(packets.presentation.canonical_marker, pending)
                self.assertEqual(packets.presentation.counter, 12)
                initial = decode_bootstrap(packets[0][1])["myG"]
                phase, initial_orders, initial_progress, index, turn = timeline_fields(
                    initial
                )
                self.assertEqual((phase, turn), (1, 12))
                self.assertEqual(initial_orders[0][index], 100)
                self.assertIn(100, initial_orders[0])
                self.assertNotIn(summon.id, initial_orders[0])

                resume = packets.presentation.resume_packets[0][1]
                phase, orders, progress, index, turn = timeline_fields(resume[15:])
                self.assertEqual((phase, turn), (1, 13))
                self.assertEqual(orders[0], original_order)
                self.assertEqual(orders[0][index], original_current)
                self.assertEqual(
                    progress,
                    {
                        int(identity): value
                        for identity, value in original_counters.items()
                    },
                )
                self.assertEqual(counters(fight), original_counters)
                self.assertEqual(fight.order, list(original_order))
                self.assertEqual(fight.current.id, original_current)
                self.assertEqual(shared.ack.received, {1})
                self.assertEqual(source_snapshot(fight), before)

    def test_unknown_historical_marker_remains_deferred_initial(self):
        fight, summon, shared = fixture(True)
        marker = (
            (
                12502,
                struct.pack(">iiiqii", fight.id, 40, -1, 999999, -1, 0),
            ),
            (13420, struct.pack(">i", fight.id)),
        )
        shared.ack = SimpleNamespace(turn=None, received={1})
        shared.reconnect_end_turn_history = (12, marker)
        before = source_snapshot(fight)
        packets = owned_snapshot(
            fight,
            shared,
            SimpleNamespace(account_id=1, character_id=100),
            actor_payload=lambda *args: (b"owned-stats", b"\x00\x00"),
        )
        phase, order, _, index, turn = timeline_fields(
            decode_bootstrap(packets[0][1])["myG"]
        )
        self.assertEqual((phase, index, turn), (0, -1, 13))
        self.assertNotIn(summon.id, order[0])
        self.assertEqual(packets.presentation.marker_packets, ())
        self.assertEqual(packets.presentation.counter, 13)
        recovery = packets.presentation.resume_packets[0][1]
        phase, orders, progress, index, turn = timeline_fields(recovery[15:])
        self.assertEqual((phase, turn), (1, 13))
        self.assertEqual(orders[0][index], fight.current.id)
        self.assertEqual(
            progress,
            {
                int(identity): value
                for identity, value in fight.native_timeline_member_counters.items()
            },
        )
        self.assertEqual(source_snapshot(fight), before)

    def test_birth_fence_restores_full_progress_and_actual_current_without_duplicates(
        self,
    ):
        for current_summon in (False, True):
            with self.subTest(current_summon=current_summon):
                fight, summon, shared = fixture(current_summon)
                before = source_snapshot(fight)
                packets = owned_snapshot(
                    fight,
                    shared,
                    SimpleNamespace(account_id=1),
                    actor_payload=lambda *args: (b"owned-stats", b"\x00\x00"),
                )
                bootstrap = decode_bootstrap(packets[0][1])
                self.assertNotIn(
                    summon.id,
                    [actor["actor_id"] for actor in bootstrap["participants"]],
                )
                phase, orders, progress, index, _ = timeline_fields(bootstrap["myG"])
                self.assertEqual((phase, index), (0, -1))
                self.assertNotIn(summon.id, orders[0])
                birth = fight.native_summon_creation_deliveries[summon.id]
                birth_packet = (birth["opcode"], bytes.fromhex(birth["payload_hex"]))
                self.assertEqual(packets.count(birth_packet), 1)
                birth_index = packets.index(birth_packet)
                action_index = next(
                    i for i, (opcode, _) in enumerate(packets) if opcode == 12514
                )
                self.assertLess(action_index, birth_index)
                self.assertEqual(sum(opcode == 12514 for opcode, _ in packets), 1)
                self.assertEqual(
                    packets[birth_index + 1], (13420, struct.pack(">i", fight.id))
                )
                early_index, early = next(
                    (i, body) for i, (op, body) in enumerate(packets) if op == 12053
                )
                self.assertLess(early_index, action_index)
                self.assertEqual(early[15:], bootstrap["myG"])
                self.assertNotIn(13912, [opcode for opcode, _ in packets])
                self.assertEqual(packets.presentation.counter, 13)
                self.assertEqual(packets.presentation.actor_ids, (summon.id,))
                # Only the real native witness releases this frozen tail.
                continuation = packets.presentation.resume_packets
                recovery_index, recovery = next(
                    (i, body)
                    for i, (op, body) in enumerate(continuation)
                    if op == 12053
                )
                self.assertEqual(recovery_index, 0)
                phase, orders, progress, index, turn = timeline_fields(recovery[15:])
                self.assertEqual(phase, 1)
                self.assertEqual(turn, 13)
                self.assertEqual(progress[summon.id], 3)
                self.assertEqual(orders[0].count(summon.id), 1)
                self.assertEqual(orders[0][index], fight.current.id)
                reset_ids = [
                    decode_actor_state(op, body)["actor_id"]
                    for op, body in continuation
                    if op == 13912
                ]
                self.assertEqual(reset_ids, [summon.id])
                restored_ids = [
                    decode_actor_state(op, body)["actor_id"]
                    for op, body in continuation
                    if op == 12873
                ]
                self.assertEqual(set(restored_ids), set(fight.actors))
                self.assertEqual(source_snapshot(fight), before)


if __name__ == "__main__":
    unittest.main()
