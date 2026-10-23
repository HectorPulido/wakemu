"""Reconnect constructs each summon before authoritative timeline restoration."""
from copy import deepcopy
from types import SimpleNamespace
import struct
import unittest

from test_combat_runtime_messages import RuntimeMessageTests
from wakfu_server.combat_reconnect_snapshot import owned_snapshot
from wakfu_server.combat_geometry_snapshot import source_snapshot
from wakfu_server.combat_wire import decode_bootstrap


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
                recovery_index, recovery = next(
                    (i, body) for i, (op, body) in enumerate(packets) if op == 12053
                )
                self.assertLess(birth_index + 1, recovery_index)
                phase, orders, progress, index, turn = timeline_fields(recovery[15:])
                self.assertEqual(phase, 1)
                self.assertEqual(turn, 13)
                self.assertEqual(progress[summon.id], 3)
                self.assertEqual(orders[0].count(summon.id), 1)
                self.assertEqual(orders[0][index], fight.current.id)
                self.assertEqual(packets[recovery_index + 1][0], 13912)
                self.assertEqual(source_snapshot(fight), before)


if __name__ == "__main__":
    unittest.main()
