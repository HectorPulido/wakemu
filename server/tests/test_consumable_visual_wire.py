"""Original native HMI wire for actual consumable transformation plans."""
import copy
import json
from pathlib import Path
import struct
import unittest
from unittest.mock import patch

from wakfu_server.consumable_buff_wire import delta, snapshot
from wakfu_server.wire import proto_fields


class ConsumableVisualWireTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = Path(__file__).parents[1] / "protocol/native-consumable-actions.json"
        rows = json.loads(path.read_text())["items"]
        cls.plans = {
            row["plan"]["states"][0]["state_id"]: row["plan"]["states"][0]
            for row in rows
            if row["native_type"] == 738 and row["item_ref"] in (10363, 10380)
        }

    @classmethod
    def state(cls, state_id, uid, stamp, remaining=300_000):
        plan = copy.deepcopy(cls.plans[state_id])
        plan.update(uid=uid, clock="online", remaining_ms=remaining)
        plan["metadata"]["native_visual_applied_at_ms"] = stamp
        return plan

    @staticmethod
    def character(states, *, breed=1, sex=0):
        return {"id": 42, "breed": breed, "sex": sex, "consumable_states": list(states)}

    @staticmethod
    def frame(opcode, packet):
        if opcode == 13420:
            return None
        if opcode == 13560:
            fight, action, _sequence, effect_class, size = struct.unpack_from(
                ">iiiih", packet
            )
            payload = packet[18 : 18 + size]
            return fight, action, effect_class, payload
        (
            fight,
            action,
            _parent,
            execute_children,
            effect_class,
            size,
        ) = struct.unpack_from(">iiiBih", packet)
        payload = packet[19 : 19 + size]
        return fight, action, execute_children, effect_class, payload

    @staticmethod
    def visual_rows(packets, opcode):
        rows = []
        for packet_opcode, packet in packets:
            if packet_opcode != opcode:
                continue
            header = ConsumableVisualWireTests.frame(packet_opcode, packet)
            if opcode == 12613 and header[3] == 400:
                rows.append((header, dict(proto_fields(header[4]))))
            elif opcode == 13560 and header[2] == 400:
                rows.append((header, dict(proto_fields(header[3]))))
        return rows

    def test_actual_state531_feca_snapshot_keeps_two_null_hmi_roots(self):
        # Native state 531 has two selected roots for a male Feca: the model
        # change and its unconditional color operation.
        character = self.character([self.state(531, 9001, 100)])
        with patch("wakfu_server.combat_conditions.canonical_aliases", return_value={}):
            packets = snapshot(character, allocate_action=iter(range(1, 30)).__next__)

        applications = self.visual_rows(packets, 12613)
        self.assertEqual([row[1][3 << 3] for row in applications], [25601, 71553])
        self.assertEqual(
            [opcode for opcode, _ in packets], [12613, 12613, 12613, 13420]
        )
        classes = [
            self.frame(opcode, packet)[3]
            for opcode, packet in packets
            if opcode == 12613
        ]
        self.assertEqual(classes, [310, 400, 400])
        self.assertEqual(packets[-1], (13420, struct.pack(">i", -1)))

        for header, fields in applications:
            # eIK=false retains the native runner but prevents a second
            # gameplay/application pass. The state and level are carried in
            # the real PL1 container and its original remaining-time context.
            packet = next(
                packet
                for opcode, packet in packets
                if opcode == 12613
                and self.frame(opcode, packet)[3] == 400
                and dict(proto_fields(self.frame(opcode, packet)[4])) == fields
            )
            self.assertEqual(packet[12], 0)
            self.assertEqual(fields[9 << 3], 1)
            self.assertEqual(fields[10 << 3], (531 << 16) | 1)
            timing = dict(proto_fields(fields[11 << 3 | 2]))
            self.assertEqual(timing[8], 0)
            self.assertEqual(timing[16], (1 << 64) - 1)
            self.assertEqual(timing[32], 300_000)
            self.assertEqual(timing[40], 0)

    def test_replay_orders_multiple_states_by_durable_stamp_and_removes_in_reverse(
        self,
    ):
        later = self.state(531, 9001, 200)
        earlier = self.state(949, 9002, 100)
        character = self.character([later, earlier])
        with patch("wakfu_server.combat_conditions.canonical_aliases", return_value={}):
            packets = snapshot(character, allocate_action=iter(range(1, 60)).__next__)

        applications = self.visual_rows(packets, 12613)
        self.assertEqual(
            [fields[3 << 3] for _, fields in applications], [43974, 25601, 71553]
        )
        # The two native state carriers remain distinct from the three actual
        # selected HMI roots. In particular, no synthetic display child is
        # duplicated for the roots already represented by the HMI packets.
        classes = [
            self.frame(opcode, packet)[3]
            for opcode, packet in packets
            if opcode == 12613
        ]
        self.assertEqual(classes, [310, 310, 400, 400, 400])

        with patch("wakfu_server.combat_conditions.canonical_aliases", return_value={}):
            removals = delta(
                character,
                self.character([]),
                allocate_action=iter(range(100, 160)).__next__,
            )
        self.assertEqual(
            [fields[3 << 3] for _, fields in self.visual_rows(removals, 13560)],
            [71553, 25601, 43974],
        )
        self.assertEqual(removals[-1], (13420, struct.pack(">i", -1)))

    def test_countdown_is_not_a_delta_but_same_uid_refresh_is_remove_then_apply(self):
        before = self.character([self.state(531, 9001, 100, remaining=250_000)])
        ticking = self.character([self.state(531, 9001, 100, remaining=249_000)])
        refreshed = self.character([self.state(531, 9001, 101, remaining=250_000)])
        with patch("wakfu_server.combat_conditions.canonical_aliases", return_value={}):
            self.assertEqual(delta(before, ticking), ())
            packets = delta(
                before, refreshed, allocate_action=iter(range(1, 30)).__next__
            )

        self.assertEqual(
            [opcode for opcode, _ in packets], [13560, 13560, 12613, 12613, 13420]
        )
        removals = self.visual_rows(packets, 13560)
        applications = self.visual_rows(packets, 12613)
        self.assertEqual([fields[3 << 3] for _, fields in removals], [71553, 25601])
        self.assertEqual([fields[3 << 3] for _, fields in applications], [25601, 71553])
        self.assertEqual(
            {fields[3 << 3]: fields[1 << 3] for _, fields in removals},
            {fields[3 << 3]: fields[1 << 3] for _, fields in applications},
        )


if __name__ == "__main__":
    unittest.main()
