"""Native world carrier delivery for owned consumable states."""
import struct
import unittest

from wakfu_server.consumable_buff_wire import delta, snapshot
from wakfu_server.wire import proto_fields


class ConsumableBuffWireTests(unittest.TestCase):
    @staticmethod
    def native_payload_fields(opcode, packet):
        if opcode == 13560:
            _fight, _action, _sequence, _effect_class, size = struct.unpack_from(
                ">iiiih", packet
            )
            offset = 18
        else:
            (
                _fight,
                _action,
                _parent,
                _execute,
                _effect_class,
                size,
            ) = struct.unpack_from(">iiiBih", packet)
            offset = 19
        return dict(proto_fields(packet[offset : offset + size]))

    @staticmethod
    def character(*, remaining=12_000, level=10, display_effect=False):
        state = dict(
            uid=9_001, state_id=1210, level=level, clock="wall", remaining_ms=remaining
        )
        if display_effect:
            state["metadata"] = {
                "native_effects": {
                    "64546": dict(
                        id=64546,
                        generic=122,
                        values=[10],
                        stat_id=21,
                        display=True,
                    ),
                }
            }
        return {
            "id": 42,
            "consumable_states": [state],
        }

    def test_snapshot_publishes_native_world_carrier_without_child_execution(self):
        packets = snapshot(self.character())

        self.assertEqual([opcode for opcode, _ in packets], [12613, 13420])
        body = packets[0][1]
        (
            fight,
            _action,
            parent,
            execute_children,
            effect_class,
            size,
        ) = struct.unpack_from(">iiiBih", body)
        self.assertEqual(
            (fight, parent, execute_children, effect_class), (-1, -1, 0, 310)
        )
        self.assertEqual(len(body), 19 + size)
        self.assertEqual(packets[-1], (13420, struct.pack(">i", -1)))
        carrier = self.native_payload_fields(12613, body)
        self.assertEqual(carrier[9 << 3], 1)  # Native display grouping PL.
        self.assertEqual(carrier[10 << 3], (1210 << 16) | 10)
        # Native carrier UID appears in both effect identity and Add13; state
        # 1210/level10 is the packed native state reference in Add10/Add13.
        # Protocol integers use protobuf varints, including signed identity
        # values represented as their native 64-bit encoding.
        self.assertIn(b"\x08\xa9\x46", body)
        self.assertIn(b"\x20\x8a\x80\xe8\x25", body)

    def test_refresh_removes_then_reapplies_same_uid_once(self):
        before = self.character(remaining=5_000)
        after = self.character(remaining=8_000, level=11)
        packets = delta(before, after)

        self.assertEqual([opcode for opcode, _ in packets], [13560, 12613, 13420])
        self.assertEqual(packets[0][1][:4], struct.pack(">i", -1))
        self.assertEqual(packets[1][1][:4], struct.pack(">i", -1))
        self.assertIn(b"\x08\xa9\x46", packets[0][1])
        self.assertIn(b"\x08\xa9\x46", packets[1][1])
        for opcode, body in packets[:2]:
            carrier = self.native_payload_fields(opcode, body)
            self.assertEqual(carrier[9 << 3], 1)
            self.assertEqual(
                carrier[10 << 3], (1210 << 16) | (10 if opcode == 13560 else 11)
            )
        self.assertEqual(packets[-1], (13420, struct.pack(">i", -1)))

    def test_removal_carries_complete_initialized_native_time_datas(self):
        before = self.character(remaining=600_000, display_effect=True)
        after = {"id": before["id"], "consumable_states": []}
        packets = delta(before, after)

        self.assertEqual(packets[-1], (13420, struct.pack(">i", -1)))
        removals = [packet for opcode, packet in packets[:-1] if opcode == 13560]
        self.assertTrue(removals)
        for packet in removals:
            uid = struct.unpack_from(">q", packet, len(packet) - 8)[0]
            carrier = self.native_payload_fields(13560, packet)
            timing = carrier[11 << 3 | 2]
            fields = dict(proto_fields(timing))
            # Original client iB.isInitialized() requires fields 1–4 and the
            # nested ix fields 1–3. Both carrier and visible child must notify
            # unapplication so aVz retires them from the native UI manager.
            self.assertEqual(set(fields), {8, 16, 26, 32, 40})
            self.assertEqual(fields[8], 1)
            self.assertEqual(fields[16], (1 << 64) - 1)
            self.assertEqual(fields[32], 600_000)
            self.assertEqual(fields[40], 0)
            nested = dict(proto_fields(fields[26]))
            self.assertEqual(set(nested), {8, 16, 24})
            self.assertEqual(nested[8], 0)
            self.assertEqual(nested[16], (1 << 64) - 1)
            self.assertEqual(nested[24], 0)
            if uid != 9_001:
                self.assertEqual(carrier[3 << 3], 64_546)
                self.assertEqual(carrier[4 << 3], 10)
                additional = dict(proto_fields(carrier[8 << 3 | 2]))
                self.assertEqual(additional[12 << 3], 21)
                self.assertEqual(additional[25 << 3], 0)

    def test_declined_or_expired_carrier_emits_no_queue(self):
        self.assertEqual(snapshot(self.character(remaining=0)), ())
        self.assertEqual(
            delta(self.character(remaining=0), self.character(remaining=0)), ()
        )

    def test_event_state_uses_native_negative_realtime_sentinel(self):
        event = {
            "id": 42,
            "consumable_states": [
                dict(
                    uid=9_002,
                    state_id=4436,
                    level=10,
                    clock="event",
                    duration_ms=0,
                    remaining_ms=0,
                    metadata={"native_realtime_duration_base": -1_000},
                )
            ],
        }
        packets = snapshot(event)
        self.assertEqual([opcode for opcode, _ in packets], [12613, 13420])
        # Native Additional22 encodes signed longs as protobuf varints.
        self.assertIn(b"\x98\xf8\xff\xff\xff\xff\xff\xff\xff\x01", packets[0][1])
        self.assertEqual(self.native_payload_fields(12613, packets[0][1])[9 << 3], 1)
        self.assertEqual(
            self.native_payload_fields(12613, packets[0][1])[10 << 3], (4436 << 16) | 10
        )

        changed = {
            **event,
            "consumable_states": [dict(event["consumable_states"][0], level=11)],
        }
        self.assertEqual(
            [opcode for opcode, _ in delta(event, changed)], [13560, 12613, 13420]
        )

        invalid = {
            **event,
            "consumable_states": [dict(event["consumable_states"][0], metadata={})],
        }
        with self.assertRaisesRegex(ValueError, "sentinel"):
            snapshot(invalid)

    def test_delta_rejects_another_actor_baseline(self):
        with self.assertRaisesRegex(ValueError, "another actor"):
            delta(self.character(), dict(id=43, consumable_states=[]))


if __name__ == "__main__":
    unittest.main()
