"""Native penalty display children retain zero deltas and initialized timing."""
import struct
import unittest

from wakfu_server.consumable_buff_wire import snapshot, delta, _child, _display_effect
from wakfu_server.wire import proto_fields


def character(level=1):
    defs = {}
    for identity, generic, runner in (
        (254573, 986, "eZI"),
        (282494, 986, "eZI"),
        (254576, 192, "eWO"),
    ):
        defs[str(identity)] = dict(
            id=identity,
            generic=generic,
            runner=runner,
            stat_id=None,
            values=[-10],
            display=True,
        )
    root = 254573 if level < 10 else 282494
    return dict(
        id=40,
        consumable_states=[
            dict(
                uid=9001,
                state_id=981,
                level=level,
                remaining_ms=120000,
                clock="online",
                effect_ids=[root, 254576],
                metadata=dict(native_effects=defs),
            )
        ],
    )


class ConsumablePenaltyDisplayTests(unittest.TestCase):
    def test_active_native_percentage_root_and_zero_codec_show_level_and_time(self):
        for level, reference in ((1, 254573), (9, 254573), (10, 282494), (100, 282494)):
            with self.subTest(level=level):
                char = character(level)
                self.assertEqual(
                    _display_effect(char["consumable_states"][0])["id"], reference
                )
                packets = snapshot(char)
                self.assertEqual([op for op, body in packets], [12613, 12613, 13420])
                for opcode, packet in packets[:2]:
                    fight, action, parent, execute, generic, size = struct.unpack_from(
                        ">iiiBih", packet
                    )
                    self.assertEqual((fight, execute), (-1, 0))
                    fields = dict(proto_fields(packet[19 : 19 + size]))
                    self.assertEqual(fields[9 << 3], 1)
                    self.assertEqual(fields[10 << 3], (981 << 16) | level)
                    if generic == 986:
                        self.assertEqual(fields[3 << 3], reference)
                        self.assertEqual(fields[4 << 3], 0)
                        additional = dict(proto_fields(fields[8 << 3 | 2]))
                        self.assertEqual(additional, {35 << 3: 0})
                removed = delta(char, dict(id=40, consumable_states=[]))
                self.assertEqual([op for op, body in removed], [13560, 13560, 13420])

    def test_native_wp_reduction_display_uses_both_zero_current_flags(self):
        row = character()["consumable_states"][0]
        effect = row["metadata"]["native_effects"]["254576"]
        uid, generic, payload = _child(40, 9001, (981, 1, 120000, "online", effect))
        self.assertEqual(generic, 192)
        fields = dict(proto_fields(payload))
        self.assertEqual(fields[4 << 3], 0)
        self.assertEqual(
            dict(proto_fields(fields[8 << 3 | 2])), {34 << 3: 0, 35 << 3: 0}
        )
